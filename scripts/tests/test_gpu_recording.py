from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave


spec = importlib.util.spec_from_file_location('gpu_recording', Path(__file__).resolve().parents[1] / 'test-gpu-recording.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def fixture():
    models = {'asr': 'OpenMOSS-Team/MOSS-Transcribe-Diarize', 'diarization': 'nvidia/Nemotron-3-Diarization'}
    segments = [{'start': .1, 'end': .9, 'text': 'Synthetic first speaker.', 'speaker_id': 'moss_S01'},
                {'start': 1, 'end': 1.9, 'text': 'Synthetic second speaker.', 'speaker_id': 'moss_S02'}]
    job = {'status': 'completed', 'profile': 'moss', 'duration': 2, 'models': models,
           'speakers': {'moss_S01': 'Speaker 1', 'moss_S02': 'Speaker 2'}, 'segments': segments}
    asr = {'model': models['asr'], 'raw_asr_text': 'Synthetic speech.'}
    diarization = {'model': models['diarization'], 'turns': [
        {'start': .1, 'end': .9, 'speaker_id': 'speaker_0'},
        {'start': 1, 'end': 1.9, 'speaker_id': 'speaker_1'}]}
    return job, asr, diarization


class RecordingHarnessTests(unittest.TestCase):
    # These validate the harness; they do not simulate or certify GPU inference.
    def test_valid_two_speaker_structure(self):
        summary = runner.validate_result(*fixture(), min_speakers=2)
        self.assertEqual(summary['transcript_speakers'], 2)
        self.assertEqual(summary['diarization_turns'], 2)

    def test_empty_speech_or_diarization_fails(self):
        for target, key in ((0, 'segments'), (1, 'raw_asr_text'), (2, 'turns')):
            values = fixture()
            values[target][key] = [] if key != 'raw_asr_text' else ''
            with self.assertRaises(runner.VerificationError):
                runner.validate_result(*values, min_speakers=1)

    def test_invalid_segment_and_turn_times_fail(self):
        for location in ('segments', 'turns'):
            for start, end in ((float('nan'), 1), (0, float('inf')), (-1, 1), (1, .5), (1, 10)):
                values = fixture()
                entries = values[0][location] if location == 'segments' else values[2][location]
                entries[0].update(start=start, end=end)
                with self.assertRaises(runner.VerificationError):
                    runner.validate_result(*values, min_speakers=1)

    def test_speaker_collapse_and_unmapped_label_fail(self):
        values = fixture()
        values[0]['segments'][1]['speaker_id'] = 'moss_S01'
        with self.assertRaisesRegex(runner.VerificationError, 'Fewer'):
            runner.validate_result(*values, min_speakers=2)
        values[0]['segments'][1]['speaker_id'] = 'unmapped'
        with self.assertRaisesRegex(runner.VerificationError, 'unmapped'):
            runner.validate_result(*values, min_speakers=1)

    def test_other_model_output_does_not_pass_as_local_gpu(self):
        values = fixture()
        values[2]['model'] = 'external-fixture'
        with self.assertRaisesRegex(runner.VerificationError, 'local MOSS and Nemotron'):
            runner.validate_result(*values, min_speakers=1)

    def test_cli_missing_gpu_fails_without_starting_installation(self):
        with tempfile.TemporaryDirectory() as name:
            audio = Path(name) / 'synthetic.wav'
            audio.write_bytes(b'synthetic fixture')
            with patch.object(sys, 'argv', ['test-gpu-recording.py', '--audio', str(audio)]), \
                 patch.object(runner.doctor, 'preflight', side_effect=RuntimeError('NVIDIA GPU not visible')), \
                 patch.object(runner.subprocess, 'run') as subprocess_run, redirect_stderr(io.StringIO()) as error:
                self.assertEqual(runner.main(), 1)
            self.assertFalse(json.loads(error.getvalue())['ok'])
            subprocess_run.assert_not_called()

    def test_timeout_cancels_only_its_own_job(self):
        client = Mock()
        client.get.return_value.json.return_value = {'status': 'transcribing'}
        with patch.object(runner.time, 'monotonic', side_effect=[0, 2]), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(runner.VerificationError, 'timeout'):
                runner.wait_for_job(client, 'fixture-job', {}, timeout=1)
        client.post.assert_called_once_with('/api/jobs/fixture-job/cancel', headers={})

    def test_model_failure_cannot_be_reported_as_success_or_echo_private_output(self):
        client = Mock()
        client.get.return_value.json.return_value = {'status': 'failed', 'error': 'private fixture transcript'}
        with redirect_stdout(io.StringIO()) as output:
            with self.assertRaises(runner.VerificationError) as failure:
                runner.wait_for_job(client, 'fixture-job', {}, timeout=1)
        self.assertNotIn('private fixture transcript', str(failure.exception) + output.getvalue())
        client.post.assert_not_called()

    def test_default_results_are_removed_even_on_failure(self):
        with self.assertRaisesRegex(RuntimeError, 'fixture'):
            with runner.result_directory(False) as directory:
                (directory / 'private.txt').write_text('synthetic')
                raise RuntimeError('fixture')
        self.assertFalse(directory.exists())

    def test_opt_in_results_are_retained_only_under_local_state(self):
        with tempfile.TemporaryDirectory() as name, patch.object(runner, 'ROOT', Path(name)), redirect_stdout(io.StringIO()):
            with runner.result_directory(True) as directory:
                (directory / 'private.txt').write_text('synthetic')
            self.assertTrue(directory.is_relative_to(Path(name) / '.local-data/gpu-tests'))
            self.assertTrue((directory / 'private.txt').is_file())

    def test_real_api_queue_normalization_and_exports_with_fixture_model_outputs(self):
        # GPU-free harness contract test: only model subprocess outputs are replaced.
        # The opt-in CLI never applies this patch and still requires real CUDA.
        if not shutil.which('ffmpeg'):
            self.skipTest('FFmpeg required for the API contract test')
        sys.path.insert(0, str(runner.ROOT / 'backend'))
        try:
            from meeting_backend.jobs import JobManager
        except ImportError:
            self.skipTest('Install backend/requirements.txt for the API contract test')
        original_run = JobManager.run
        calls = []

        def fixture_run(manager, job_id, command, log, input_data=None):
            if command[0] == 'ffmpeg':
                return original_run(manager, job_id, command, log, input_data)
            stage = command[2]
            calls.append(stage)
            job, asr, diarization = fixture()
            if stage == 'asr':
                asr.update(segments=[{**segment, 'raw_speaker_id': segment['speaker_id'][5:]}
                                     for segment in job['segments']], timing_quality='estimated_segment')
            output = Path(command[command.index('--output') + 1])
            output.write_text(json.dumps(asr if stage == 'asr' else diarization))

        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            audio = directory / 'synthetic.wav'
            with wave.open(str(audio), 'wb') as output:
                output.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                output.writeframes(bytes(16000 * 2 * 2))
            result = directory / 'results'
            result.mkdir()
            with patch.object(runner.doctor, 'check_models', return_value=[directory / 'moss', directory / 'diar']), \
                 patch.object(JobManager, 'run', fixture_run), patch.dict(os.environ), redirect_stdout(io.StringIO()):
                summary = runner.verify_recording(audio, result, min_speakers=2, timeout=20)
            self.assertEqual(calls, ['asr', 'diarize'])
            self.assertTrue(summary['ok'])
            self.assertTrue(summary['original_preserved'])
            self.assertTrue(summary['exports_verified'])
            self.assertEqual(summary['transcript_speakers'], 2)
            self.assertTrue((result / 'transcript.md').is_file())


if __name__ == '__main__':
    unittest.main()
