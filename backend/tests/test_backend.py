import json
import subprocess
import sys
import threading
import time
import wave
import pytest
from pathlib import Path

from fastapi.testclient import TestClient

from meeting_backend.alignment import align, joint_segments
from meeting_backend.app import create_app
from meeting_backend.jobs import Cancelled, JobManager
from meeting_backend.storage import Store, now


def job_record(job_id='fixture'):
    return dict(id=job_id, title='회의', filename='meeting.wav', original_suffix='.wav', created_at=now(),
                status='queued', progress=0, profile='whisper-int8', duration=None, error=None,
                segments=[], speakers={}, rules='', minutes='', raw_asr_text='')


class PausedManager(JobManager):
    """Explicit test fixture: imports queue but do not run GPU inference."""
    def start(self):
        pass


def test_alignment_distinguishes_overlap_from_speaker_change():
    asr = {'segments': [{'start': 0, 'end': 4, 'text': '하나 둘 셋', 'words': [
        {'start': 0, 'end': 1, 'text': '하나'}, {'start': 1, 'end': 2, 'text': ' 둘'},
        {'start': 3, 'end': 4, 'text': ' 셋'}]}]}
    turns = [dict(start=0, end=1.6, speaker_id='a'), dict(start=1.3, end=2, speaker_id='b')]
    segments = align(asr, turns)
    assert segments[1]['overlap'] and segments[1]['speaker_candidates'] == ['b', 'a']
    assert segments[2]['speaker_id'] == 'unknown'
    sequential = align({'segments': [{'start': 0, 'end': 2, 'text': '경계', 'words': []}]}, [
        dict(start=0, end=1, speaker_id='a'), dict(start=1, end=2, speaker_id='b')])[0]
    assert not sequential['overlap']
    assert sequential['review_flags'] == ['speaker_boundary', 'approximate_timing']


def test_api_auth_edit_export_range_and_reload(tmp_path):
    app = create_app(tmp_path, token='test-secret', manager_factory=PausedManager)
    with TestClient(app, base_url='http://localhost') as client:
        assert client.get('/api/jobs').status_code == 401
        assert client.get('/health').json()['default_profile'] == 'moss'
        assert client.get('/health', headers={'Host': 'evil.example'}).status_code == 400
        client.headers['Authorization'] = 'Bearer test-secret'
        content = b'preserved-original-audio'
        response = client.post('/api/jobs', files={'file': ('../../meeting.m4a', content)})
        assert response.status_code == 201
        assert response.json()['profile'] == 'moss'
        job_id = response.json()['id']
        store = app.state.store
        segment = align({'segments': [{'start': 1, 'end': 2, 'text': '원문'}]},
                        [dict(start=1, end=2, speaker_id='speaker_0')])[0]
        store.update(job_id, status='completed', segments=[segment], speakers={'speaker_0': '화자 1'}, raw_asr_text='원문')
        response = client.patch(f'/api/jobs/{job_id}', json={
            'title': '수정된 회의', 'segments': [{'id': '0', 'text': '수정'}],
            'speakers': {'speaker_0': '참석자'}, 'rules': '정확히', 'minutes': '회의록'})
        assert response.status_code == 200
        result = response.json()
        assert result['segments'][0]['speaker_name'] == '참석자'
        assert result['segments'][0]['original_text'] == '원문'
        assert result['raw_asr_text'] == '원문'
        assert result['segments'][0]['text'] == '수정'
        assert client.patch(f'/api/jobs/{job_id}', json={'segments': [{'id': 'missing', 'text': 'bad'}]}).status_code == 400
        data = client.get(f'/api/jobs/{job_id}/export?format=json').json()
        assert data['rules'] == '정확히'
        markdown = client.get(f'/api/jobs/{job_id}/export?format=markdown').text
        assert '00:00:01.000' in markdown and '참석자' in markdown and 'approximate_timing' in markdown
        audio = client.get(f'/api/jobs/{job_id}/audio', headers={'Range': 'bytes=0-8'})
        assert audio.status_code == 206 and audio.content == content[:9]
        assert client.get(f'/api/jobs/{job_id}/audio').content == content
    loaded = Store(tmp_path).get(job_id)
    assert loaded['minutes'] == '회의록' and loaded['status'] == 'completed'
    assert (tmp_path / job_id / 'original.m4a').read_bytes() == content


def test_restart_marks_unfinished_job_failed(tmp_path):
    Store(tmp_path).save(job_record())
    loaded = Store(tmp_path).get('fixture')
    assert loaded['status'] == 'failed'
    assert 'restarted' in loaded['error']


def test_cancel_terminates_only_owned_child(tmp_path):
    store = Store(tmp_path)
    store.save(job_record())
    manager = JobManager(store)
    manager.active_id = 'fixture'
    errors = []
    def execute():
        try:
            manager.run('fixture', [sys.executable, '-c', 'import time; time.sleep(30)'], tmp_path / 'child.log')
        except Cancelled:
            errors.append('cancelled')
    unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    thread = threading.Thread(target=execute)
    thread.start()
    try:
        deadline = time.monotonic() + 5
        while manager.process is None and time.monotonic() < deadline:
            time.sleep(.01)
        assert manager.process is not None
        own = manager.process
        manager.cancel('fixture')
        thread.join(timeout=5)
        assert not thread.is_alive() and own.poll() is not None
        assert unrelated.poll() is None
        assert store.get('fixture')['status'] == 'cancelled'
        assert errors == ['cancelled']
    finally:
        unrelated.terminate()
        unrelated.wait()


@pytest.mark.parametrize('profile', ['whisper-int8', 'moss', 'moss-chunked-fixture'])
def test_pipeline_keeps_original_and_orders_stages(tmp_path, monkeypatch, profile):
    """Real FFmpeg, explicit fake inference outputs; never presented as model evidence."""
    store = Store(tmp_path)
    record = job_record()
    record['profile'] = 'moss' if profile.startswith('moss') else profile
    store.save(record)
    directory = tmp_path / 'fixture'
    original = directory / 'original.wav'
    with wave.open(str(original), 'wb') as audio:
        audio.setparams((1, 2, 8000, 8000, 'NONE', 'not compressed'))
        audio.writeframes(b'\x00\x00' * 8000)
    original_bytes = original.read_bytes()
    monkeypatch.setenv('MEETING_WHISPER_MODEL', str(tmp_path))
    monkeypatch.setenv('MEETING_MOSS_MODEL', str(tmp_path))
    monkeypatch.setenv('MEETING_DIAR_MODEL', str(tmp_path))
    class FixtureManager(JobManager):
        stages = []
        def run(self, job_id, command, log):
            if len(command) > 2 and command[2] in {'asr', 'diarize'}:
                stage = command[2]
                self.stages.append(stage)
                output = Path(command[command.index('--output') + 1])
                result = ({'model': 'test-fixture', 'raw_asr_text': '시험', 'timing_quality': 'estimated_word',
                           'segments': [{'start': 0, 'end': 1, 'text': '시험', 'words': [{'start': 0, 'end': 1, 'text': '시험'}]}]}
                          if stage == 'asr' else {'turns': [{'start': 0, 'end': 1, 'speaker_id': 'speaker_0'}], 'diarization_mode': 'native_offline'})
                if stage == 'asr' and profile.startswith('moss'):
                    result['timing_quality'] = 'estimated_segment'
                    result['raw_structured_text'] = 'explicit joint fixture'
                    result['segments'][0].update(speaker_id='moss_S01', raw_speaker_id='S01', words=[])
                    if profile == 'moss-chunked-fixture':
                        result['chunks'] = [{'chunk_id': 'c0000', 'start': 0, 'end': .5}, {'chunk_id': 'c0001', 'start': .5, 'end': 1}]
                        result['segments'] = [dict(start=i * .5, end=(i + 1) * .5, text='시험', words=[],
                                                   raw_speaker_id='S01', speaker_id=f'moss_c{i:04d}_S01',
                                                   chunk_id=f'c{i:04d}', chunk_index=i, local_start=0, local_end=.5)
                                              for i in range(2)]
                output.write_text(json.dumps(result))
            else:
                super().run(job_id, command, log)
    manager = FixtureManager(store)
    manager.process_job('fixture')
    assert manager.stages == ['asr', 'diarize']
    assert store.get('fixture')['status'] == 'completed'
    assert store.get('fixture')['duration'] == 1
    assert store.get('fixture')['inference']['diarization']['diarization_mode'] == 'native_offline'
    if profile.startswith('moss'):
        completed = store.get('fixture')
        assert completed['segments'][0]['speaker_id'] == 'moss_S01'
        assert list(completed['speakers']) == ['moss_S01']
        assert completed['raw_structured_text'] == 'explicit joint fixture'
        expected_role = 'overlap_and_chunk_speaker_mapping' if profile == 'moss-chunked-fixture' else 'overlap_review_only'
        assert completed['inference']['diarization']['role'] == expected_role
        if profile == 'moss-chunked-fixture':
            assert completed['speaker_mapping_evidence']['applied']
            assert len(completed['raw_joint_chunks']) == 2
        assert completed['overlap_review_activity']['speaker_namespace'] == 'nemotron'
    assert original.read_bytes() == original_bytes
    with wave.open(str(directory / 'working.wav')) as audio:
        assert audio.getframerate() == 16000 and audio.getnchannels() == 1


def test_whisper_profile_decoding_parameters(monkeypatch):
    """Verify invocation contract without loading a model or using a GPU."""
    from types import SimpleNamespace
    from meeting_backend.worker import asr
    calls = {}
    class Model:
        def __init__(self, model, **kwargs):
            calls['load'] = kwargs
        def transcribe(self, audio, **kwargs):
            calls['decode'] = kwargs
            word = SimpleNamespace(start=0, end=1, word=' 시험', probability=.9)
            segment = SimpleNamespace(start=0, end=1, text=' 시험', words=[word])
            return iter([segment]), None
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=Model))
    result = asr(SimpleNamespace(profile='whisper-int8', model='explicit-test-fixture', audio='fixture.wav'))
    assert calls['load']['compute_type'] == 'int8_float16'
    assert calls['decode'] == {'language': 'ko', 'beam_size': 1, 'temperature': 0,
                               'condition_on_previous_text': False, 'vad_filter': True, 'word_timestamps': True}
    assert result['precision'] == 'int8_float16'
    assert result['segments'][0]['words'][0]['text'] == ' 시험'


def test_joint_speakers_preserved_and_overlap_review_separate():
    source = {'segments': [
        {'start': 0, 'end': 2, 'text': '원문 하나', 'speaker_id': 'moss_S02', 'raw_speaker_id': 'S02'},
        {'start': 1.5, 'end': 3, 'text': '원문 둘', 'speaker_id': 'moss_S01', 'raw_speaker_id': 'S01'},
        {'start': 4, 'end': 5, 'text': '원문 셋', 'speaker_id': 'moss_S02', 'raw_speaker_id': 'S02'},
    ]}
    activity = [dict(start=0, end=5, speaker_id='speaker_7'),
                dict(start=4.2, end=4.8, speaker_id='speaker_3')]
    segments = joint_segments(source, activity, 5)
    assert [s['speaker_id'] for s in segments] == ['moss_S02', 'moss_S01', 'moss_S02']
    assert [(s['start'], s['end'], s['text']) for s in segments] == [(s['start'], s['end'], s['text']) for s in source['segments']]
    assert segments[0]['overlap_sources'] == ['moss_joint_segments']
    assert segments[2]['overlap_sources'] == ['nemotron_activity']
    assert all(s['overlap'] and s['timing_quality'] == 'estimated_segment' for s in segments)
    assert all(s['speaker_candidates'][0].startswith('moss_') for s in segments)


@pytest.mark.parametrize('start,end', [(float('nan'), 1), (0, float('inf')), (-1, 1), (2, 1), (0, 6)])
def test_joint_invalid_timestamps_fail_without_inventing_times(start, end):
    with pytest.raises(ValueError, match='invalid timestamp'):
        joint_segments({'segments': [dict(start=start, end=end, text='x', speaker_id='moss_S01', raw_speaker_id='S01')]}, [], 5)


def test_moss_chunks_cover_entire_recording_without_gaps():
    from meeting_backend.moss_chunks import frame_ranges
    frames = 601 * 16000 + 123
    chunks = frame_ranges(frames, 16000)
    assert chunks == [(0, 4800000), (4800000, 9600000), (9600000, frames)]
    assert sum(end - start for start, end in chunks) == frames
    assert all(end - start <= 300 * 16000 for start, end in chunks)


def test_moss_local_validation_precedes_global_offsets():
    from types import SimpleNamespace
    from meeting_backend.moss_chunks import convert_segments
    parsed = [SimpleNamespace(start=1, end=2, speaker='S01', text='그대로')]
    multi = convert_segments(parsed, 1, 4800000, 9600000, 16000, True)[0]
    assert multi['speaker_id'] == 'moss_c0001_S01'
    assert (multi['start'], multi['end']) == (301, 302)
    assert (multi['local_start'], multi['local_end']) == (1, 2)
    single = convert_segments(parsed, 0, 0, 4800000, 16000, False)[0]
    assert single['speaker_id'] == 'moss_S01'
    with pytest.raises(ValueError, match='invalid local timestamp'):
        convert_segments(parsed, 1, 4800000, 4816000, 16000, True)


def test_moss_truncated_generation_cannot_silently_succeed():
    from meeting_backend.moss_chunks import check_completion
    check_completion({'text': '[0.0][S01]정상[1.0]', 'generated_tokens': 20}, [object()])
    for output in [
        {'text': '[0.0][S01]정상[1.0]', 'generated_tokens': 16384},
        {'text': '[0.0][S01]정상[1.0][2.0][S02]잘린 말', 'generated_tokens': 40},
        {'text': '[0.0][S01]정상[1.0][2.0][S02]잘린 말[', 'generated_tokens': 40},
    ]:
        with pytest.raises(RuntimeError):
            check_completion(output, [object()])


def test_chunk_boundary_review_flags_only_internal_cuts():
    from types import SimpleNamespace
    from meeting_backend.moss_chunks import convert_segments
    local = [SimpleNamespace(start=0, end=1, speaker='S01', text='시작'),
             SimpleNamespace(start=298, end=300, speaker='S01', text='끝')]
    first = convert_segments(local, 0, 0, 4800000, 16000, True)
    last = convert_segments(local, 1, 4800000, 9600000, 16000, True, is_last=True)
    assert first[0]['review_flags'] == [] and first[1]['review_flags'] == ['chunk_boundary']
    assert last[0]['review_flags'] == ['chunk_boundary'] and last[1]['review_flags'] == []
    aligned = joint_segments({'segments': first + last}, [], 600)
    assert aligned[1]['review_flags'] == ['chunk_boundary']
    assert aligned[2]['review_flags'] == ['chunk_boundary']
