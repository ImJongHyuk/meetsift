"""Opt-in GPU integration test with a user-supplied recording; never a CI GPU claim."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
import uuid

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
API_PYTHON = ROOT / 'backend/.venv/bin/python'
sys.path.insert(0, str(SCRIPTS))
import doctor


class VerificationError(RuntimeError):
    pass


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError('Must be a positive integer')
    return number


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def result_directory(keep):
    # Separate store/token: never attach to an existing service or user meeting store.
    if keep:
        directory = ROOT / '.local-data/gpu-tests' / uuid.uuid4().hex
        directory.mkdir(mode=0o700, parents=True)
        print('Private results: ' + directory.relative_to(ROOT).as_posix(), flush=True)
        yield directory
    else:
        with tempfile.TemporaryDirectory(prefix='meetsift-gpu-test-') as directory:
            yield Path(directory)


def wait_for_job(client, job_id, headers, timeout):
    deadline = time.monotonic() + timeout
    last_status = None
    try:
        while True:
            response = client.get('/api/jobs/' + job_id, headers=headers)
            response.raise_for_status()
            job = response.json()
            status = job['status']
            if status != last_status:
                print('Stage: ' + status, flush=True)
                last_status = status
            if status == 'completed':
                return job
            if status in {'failed', 'cancelled'}:
                raise VerificationError('Recording processing failed; rerun with --keep-results to inspect private worker logs.')
            if time.monotonic() >= deadline:
                raise VerificationError('Recording processing exceeded the job timeout.')
            time.sleep(1)
    finally:
        # Cancel only this test job. Also runs on Ctrl+C or a failed poll.
        if last_status not in {'completed', 'failed', 'cancelled'}:
            client.post('/api/jobs/' + job_id + '/cancel', headers=headers)


def validate_result(job, asr, diarization, min_speakers):
    duration = job.get('duration')
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise VerificationError('Invalid recording duration.')
    if job.get('profile') != 'moss' or job.get('status') != 'completed':
        raise VerificationError('The default local pipeline did not complete.')
    expected = {'asr': 'OpenMOSS-Team/MOSS-Transcribe-Diarize', 'diarization': 'nvidia/Nemotron-3-Diarization'}
    if job.get('models') != expected or asr.get('model') != expected['asr'] or diarization.get('model') != expected['diarization']:
        raise VerificationError('Expected local MOSS and Nemotron model outputs.')
    segments, turns = job.get('segments', []), diarization.get('turns', [])
    if not segments or not turns or not asr.get('raw_asr_text', '').strip():
        raise VerificationError('Empty transcript or diarization activity; supply a recording with clear speech.')
    for entries in (segments, turns):
        for entry in entries:
            start, end = entry.get('start'), entry.get('end')
            if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in (start, end)) or not 0 <= start < end <= duration + .25:
                raise VerificationError('Invalid or out-of-recording timestamps.')
    speakers = {segment.get('speaker_id') for segment in segments} - {None, '', 'unknown'}
    if any(not segment.get('text', '').strip() or segment.get('speaker_id') not in job.get('speakers', {}) for segment in segments):
        raise VerificationError('Empty segment text or unmapped speaker label.')
    if len(speakers) < min_speakers:
        raise VerificationError('Fewer transcript speakers than --min-speakers requires.')
    return {'duration_seconds': duration, 'segments': len(segments),
            'transcript_speakers': len(speakers), 'diarization_turns': len(turns)}


def verify_recording(audio, directory, min_speakers, timeout):
    # ASGI transport exercises the real API/lifespan/queue/workers without taking a port.
    # No fake workers or alternate providers are used by this command.
    from fastapi.testclient import TestClient
    sys.path.insert(0, str(ROOT / 'backend'))
    from meeting_backend.app import create_app

    native = ROOT / 'backend/.venv-native/bin/python'
    models = doctor.check_models()
    os.environ.update({'MEETING_MOSS_PYTHON': str(native), 'MEETING_DIAR_PYTHON': str(native),
                       'MEETING_MOSS_MODEL': str(models[0]), 'MEETING_DIAR_MODEL': str(models[1]),
                       'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'})
    original_hash = sha256(audio)
    headers = {'Authorization': 'Bearer ' + secrets.token_urlsafe(32)}
    token = headers['Authorization'].removeprefix('Bearer ')
    config = {'transcription': {'provider': 'local', 'model': str(models[0])},
              'diarization': {'provider': 'local', 'model': str(models[1])}}
    with TestClient(create_app(data_dir=directory, token=token), base_url='http://127.0.0.1') as client:
        if client.get('/api/jobs').status_code != 401:
            raise VerificationError('Unauthenticated job access was not rejected.')
        with audio.open('rb') as stream:
            response = client.post('/api/jobs', headers=headers,
                                   files={'file': (audio.name, stream, 'application/octet-stream')},
                                   data={'profile': 'moss', 'processing_config': json.dumps(config)})
        response.raise_for_status()
        job_id = response.json()['id']
        job = wait_for_job(client, job_id, headers, timeout)
        job_dir = directory / job_id
        asr = json.loads((job_dir / 'asr.json').read_text())
        diarization = json.loads((job_dir / 'diarization.json').read_text())
        summary = validate_result(job, asr, diarization, min_speakers)
        if job.get('original_sha256') != original_hash or sha256(audio) != original_hash:
            raise VerificationError('Input integrity check failed.')
        downloaded = client.get('/api/jobs/' + job_id + '/audio', headers=headers)
        downloaded.raise_for_status()
        if hashlib.sha256(downloaded.content).hexdigest() != original_hash:
            raise VerificationError('Original audio was not preserved by the upload/playback API.')
        exported = client.get('/api/jobs/' + job_id + '/export?format=json', headers=headers)
        markdown = client.get('/api/jobs/' + job_id + '/export?format=markdown', headers=headers)
        exported.raise_for_status()
        markdown.raise_for_status()
        if exported.json()['segments'] != job['segments'] or job['segments'][0]['text'] not in markdown.text:
            raise VerificationError('JSON or Markdown export is incomplete.')
        (directory / 'transcript.json').write_bytes(exported.content)
        (directory / 'transcript.md').write_bytes(markdown.content)
        summary.update(ok=True, original_preserved=True, exports_verified=True)
        (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audio', type=Path, required=True, help='Real recording; the entire file is processed')
    parser.add_argument('--min-speakers', type=positive_int, default=1)
    parser.add_argument('--timeout', type=positive_int, default=1800, help='Job timeout in seconds, excluding installation')
    parser.add_argument('--install-system-deps', action='store_true')
    parser.add_argument('--skip-setup', action='store_true', help='Reuse an installed environment; GPU checks still run')
    parser.add_argument('--keep-results', action='store_true', help='Keep private recordings/transcripts/logs under .local-data/gpu-tests/')
    args = parser.parse_args()
    try:
        if not args.audio.is_file() or args.audio.stat().st_size == 0:
            raise VerificationError('Supply an existing nonempty recording file.')
        doctor.preflight('gpu')
        if not args.skip_setup:
            command = ['bash', str(SCRIPTS / 'setup-backend.sh'), '--gpu']
            if args.install_system_deps:
                command.append('--system-deps')
            subprocess.run(command, check=True)
        if Path(sys.prefix).resolve() != (ROOT / 'backend/.venv').resolve():
            if not API_PYTHON.is_file():
                raise VerificationError('API environment missing; run without --skip-setup.')
            os.execv(API_PYTHON, [str(API_PYTHON), str(__file__), *sys.argv[1:], '--skip-setup'])
        subprocess.run([sys.executable, str(SCRIPTS / 'doctor.py'), '--mode', 'gpu'], check=True)
        previous_umask = os.umask(0o077)
        try:
            with result_directory(args.keep_results) as directory:
                summary = verify_recording(args.audio, directory, args.min_speakers, args.timeout)
        finally:
            os.umask(previous_umask)
        print(json.dumps(summary))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({'ok': False, 'error': 'Interrupted; any active test job was stopped.'}), file=sys.stderr)
    except subprocess.CalledProcessError:
        print(json.dumps({'ok': False, 'error': 'GPU setup or diagnostics failed; resolve the diagnostic above.'}), file=sys.stderr)
    except Exception as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
