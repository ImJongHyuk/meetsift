import json
import subprocess
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from fastapi.testclient import TestClient

from meeting_backend.app import create_app
from meeting_backend.jobs import JobManager
from meeting_backend.storage import Store, now
from meeting_backend.providers import normalize_asr, normalize_turns, request_audio, run_remote, validate_processing


def config(provider='server', model='fixture-model', base='http://127.0.0.1:9000/v1', key='fixture-private-key'):
    return dict(provider=provider, model=model, baseUrl=base, apiKey=key,
                endpoint='/audio/transcriptions', responseFormat='verbose_json', options='')


def test_openrouter_diarization_options_and_auth_are_sent_not_in_errors(tmp_path):
    audio = tmp_path / 'audio.wav'
    audio.write_bytes(b'fixture-not-real-inference')
    seen = []

    def handle(request):
        seen.append(request)
        payload = json.loads(request.content)
        assert payload['provider']['options'] == {'azure': {'diarization': {'enabled': True}}}
        assert payload['response_format'] == 'verbose_json'
        assert request.headers['Authorization'] == 'Bearer fixture-private-key'
        return httpx.Response(401, json={'error': 'fixture-private-key must never be persisted'})

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError) as error:
            request_audio(config('openrouter', 'microsoft/mai-transcribe-2', 'https://openrouter.ai/api/v1'), audio, 'diarization', client)
    assert len(seen) == 1 and 'fixture-private-key' not in str(error.value)


def test_provider_results_require_real_timestamps_and_speakers():
    with pytest.raises(ValueError, match='시간 정보'):
        normalize_asr({'text': 'timestamps absent'}, 1)
    with pytest.raises(ValueError, match='화자 ID'):
        normalize_turns({'segments': [{'start': 0, 'end': 1, 'text': 'speaker absent'}]}, 1)
    for invalid in [float('nan'), float('inf'), -1, 2]:
        with pytest.raises(ValueError):
            normalize_asr({'segments': [{'start': invalid, 'end': 1, 'text': 'invalid'}]}, 1)
    turns = normalize_turns({'segments': [{'start': 0, 'end': 1, 'speaker': 0}]}, 1)
    assert turns == [{'start': 0, 'end': 1, 'speaker_id': '0'}]


def test_provider_validation_rejects_credentials_in_urls_and_openrouter_redirects():
    for bad in ['http://user:secret@example.com/v1', 'https://example.com/v1?key=secret', 'file:///tmp/file']:
        with pytest.raises(ValueError):
            validate_processing({'transcription': config(base=bad), 'diarization': config()})
    with pytest.raises(ValueError):
        validate_processing({'transcription': config('openrouter', base='https://other.example/api/v1'), 'diarization': config()})


def test_remote_chunks_shift_times_without_claiming_shared_speaker_identity(tmp_path):
    audio = tmp_path / 'long.wav'
    with wave.open(str(audio), 'wb') as stream:
        stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        stream.writeframes(b'\0' * (301 * 16000 * 2))

    def fixture_request(config, audio, stage):
        return {'segments': [{'start': 0, 'end': .5, 'speaker': 0, 'text': 'explicit fixture'}]}

    result = run_remote(config(), audio, 'diarization', request=fixture_request)
    assert result['turns'][0]['start'] == 0
    assert result['turns'][1]['start'] == 300
    assert result['turns'][0]['speaker_id'] != result['turns'][1]['speaker_id']
    assert result['speaker_linking'] == 'independent_chunk_speakers'
    assert normalize_turns({'segments': [{'start': 0, 'end': 1, 'speaker': 0}],
                            'words': [{'start': 0, 'end': 1, 'word': 'no word speaker'}]}, 1)[0]['speaker_id'] == '0'


@pytest.mark.parametrize('remote_asr', [True, False])
def test_local_and_remote_audio_stages_can_be_mixed(tmp_path, monkeypatch, remote_asr):
    """Explicit model fixtures verify dispatch only; no GPU accuracy claim."""
    monkeypatch.setenv('MEETING_MOSS_MODEL', str(tmp_path))
    monkeypatch.setenv('MEETING_DIAR_MODEL', str(tmp_path))
    store = Store(tmp_path / 'store')
    store.save(dict(id='fixture', title='mixed stage fixture', filename='sample.wav', original_suffix='.wav',
                    created_at=now(), profile='moss', status='queued', segments=[], speakers={}, rules='', minutes=''))
    original = store.root / 'fixture' / 'original.wav'
    with wave.open(str(original), 'wb') as stream:
        stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        stream.writeframes(b'\0' * 16000)
    calls = []

    class FixtureManager(JobManager):
        def run(self, job_id, command, log, input_data=None):
            if '--stage' in command:
                stage = command[command.index('--stage') + 1]
                calls.append(('remote', stage))
                assert json.loads(input_data)['apiKey'] == 'fixture-private-key'
            elif len(command) > 2 and command[2] in {'asr', 'diarize'}:
                stage = 'transcription' if command[2] == 'asr' else 'diarization'
                calls.append(('local', stage))
            else:
                return super().run(job_id, command, log, input_data)
            target = command[command.index('--output') + 1]
            result = ({'model': 'fixture-asr', 'raw_asr_text': '혼합 검증', 'timing_quality': 'estimated_segment',
                       'segments': [{'start': 0, 'end': .4, 'text': '혼합 검증', 'speaker_id': 'moss_S01', 'raw_speaker_id': 'S01', 'words': []}]}
                      if stage == 'transcription' else {'turns': [{'start': 0, 'end': .4, 'speaker_id': 'chosen-diarizer'}]})
            from pathlib import Path
            Path(target).write_text(json.dumps(result))

    manager = FixtureManager(store)
    manager.job_configs['fixture'] = {'transcription': config('server' if remote_asr else 'local'),
                                     'diarization': config('local' if remote_asr else 'server')}
    manager.process_job('fixture')
    assert calls == [('remote' if remote_asr else 'local', 'transcription'), ('local' if remote_asr else 'remote', 'diarization')]
    assert store.get('fixture')['segments'][0]['speaker_id'] == 'chosen-diarizer'


def test_galaxy_m4a_routes_each_stage_and_never_persists_keys(tmp_path):
    """AAC/M4A fixture and real FFmpeg/HTTP subprocesses; not real model inference."""
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            calls.append((self.path, self.headers['Authorization'], body))
            data = ({'text': '갤럭시 녹음 확인', 'segments': [{'start': 0, 'end': .4, 'text': '갤럭시 녹음 확인'}]}
                    if self.path.startswith('/asr/') else {'segments': [{'start': 0, 'end': .4, 'speaker': 0}]})
            payload = json.dumps(data).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    sample = tmp_path / 'galaxy.m4a'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.5',
                    '-ar', '48000', '-ac', '2', '-c:a', 'aac', str(sample)], check=True)
    original = sample.read_bytes()
    origin = f'http://127.0.0.1:{server.server_port}'
    settings = {'transcription': config(model='asr-fixture', base=origin + '/asr', key='asr-secret-fixture'),
                'diarization': config(model='diar-fixture', base=origin + '/diar', key='diar-secret-fixture')}
    app = create_app(tmp_path / 'data', token='test-local-token')
    try:
        with TestClient(app, base_url='http://localhost', headers={'Authorization': 'Bearer test-local-token'}) as client:
            response = client.post('/api/jobs', data={'profile': 'moss', 'processing_config': json.dumps(settings)},
                                   files={'file': ('음성 001_갤럭시.M4A', original, 'audio/mp4')})
            assert response.status_code == 201
            job_id = response.json()['id']
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                job = client.get(f'/api/jobs/{job_id}').json()
                if job['status'] in {'completed', 'failed'}:
                    break
                time.sleep(.05)
            assert job['status'] == 'completed', job.get('error')
            assert job['segments'][0]['text'] == '갤럭시 녹음 확인'
            assert job['segments'][0]['speaker_id'] == 'remote_c0000_0'
            assert job['models'] == {'asr': 'asr-fixture', 'diarization': 'diar-fixture'}
            audio = client.get(f'/api/jobs/{job_id}/audio')
            assert audio.content == original and audio.headers['content-type'].startswith('audio/mp4')
            exported = client.get(f'/api/jobs/{job_id}/export').text
            assert 'asr-secret-fixture' not in exported and 'diar-secret-fixture' not in exported
            assert calls[0][0] == '/asr/audio/transcriptions' and calls[0][1] == 'Bearer asr-secret-fixture'
            assert b'asr-fixture' in calls[0][2]
            assert calls[1][0] == '/diar/audio/transcriptions' and calls[1][1] == 'Bearer diar-secret-fixture'
            assert b'diar-fixture' in calls[1][2]
        for path in (tmp_path / 'data').rglob('*'):
            if path.is_file():
                assert b'asr-secret-fixture' not in path.read_bytes()
                assert b'diar-secret-fixture' not in path.read_bytes()
        assert not app.state.manager.job_configs
    finally:
        server.shutdown()
        server.server_close()
