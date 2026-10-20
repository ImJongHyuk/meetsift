import json
import os
import queue
import signal
import subprocess
import sys
import threading
import wave
from pathlib import Path

from .alignment import align, joint_segments
from .storage import TERMINAL

PROFILES = ['moss', 'whisper-int8', 'whisper-fp16', 'qwen-ko']
DEFAULT_PROFILE = 'moss'
WORKER = Path(__file__).with_name('worker.py')


class Cancelled(Exception):
    pass


class JobManager:
    def __init__(self, store):
        self.store = store
        self.queue = queue.Queue()
        self.lock = threading.RLock()
        self.cancelled = set()
        self.process = None
        self.active_id = None
        self.thread = None
        self.job_configs = {}

    def start(self):
        self.thread = threading.Thread(target=self.loop, daemon=True, name='meeting-worker')
        self.thread.start()

    def close(self):
        with self.lock:
            for job in self.store.list():
                if job['status'] not in TERMINAL:
                    self.cancel(job['id'])
        self.queue.put(None)
        if self.thread:
            self.thread.join(timeout=10)

    def submit(self, job_id, processing_config=None):
        if processing_config is not None:
            self.job_configs[job_id] = processing_config
        self.queue.put(job_id)

    def cancel(self, job_id):
        with self.lock:
            job = self.store.get(job_id)
            if job['status'] in TERMINAL:
                return job
            self.cancelled.add(job_id)
            if self.active_id == job_id and self.process and self.process.poll() is None:
                self.terminate(self.process)
            return self.store.update(job_id, status='cancelled', error=None)

    @staticmethod
    def terminate(process):
        # Own process group only: never pkill or touch unrelated GPU workloads.
        try:
            if os.name == 'posix':
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                if os.name == 'posix':
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait(timeout=3)
        except ProcessLookupError:
            pass

    def check(self, job_id):
        if job_id in self.cancelled:
            raise Cancelled()

    def stage(self, job_id, status, progress):
        with self.lock:
            self.check(job_id)
            self.store.update(job_id, status=status, progress=progress)

    def run(self, job_id, command, log, input_data=None):
        with log.open('ab') as output:
            with self.lock:
                self.check(job_id)
                process = subprocess.Popen(command, stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL, stdout=output, stderr=output,
                                           start_new_session=os.name == 'posix')
                self.process = process
            if input_data is not None:
                process.communicate(input_data)
            code = process.wait()
            with self.lock:
                self.process = None
                self.check(job_id)
            if code:
                # Keep useful model/FFmpeg error detail; bounded to avoid flooding UI.
                detail = log.read_bytes()[-3000:].decode('utf-8', errors='replace')
                raise RuntimeError(f'{Path(command[0]).name} exited with {code}: {detail}')

    def loop(self):
        while (job_id := self.queue.get()) is not None:
            try:
                with self.lock:
                    self.check(job_id)
                    self.active_id = job_id
                self.process_job(job_id)
            except Cancelled:
                pass
            except Exception as error:
                with self.lock:
                    if job_id not in self.cancelled:
                        self.store.update(job_id, status='failed', error=str(error))
            finally:
                with self.lock:
                    self.active_id = None
                    self.process = None
                    self.job_configs.pop(job_id, None)

    def process_job(self, job_id):
        job = self.store.get(job_id)
        config = self.job_configs.get(job_id, {})
        transcription = config.get('transcription', {'provider': 'local'})
        diar_config = config.get('diarization', {'provider': 'local'})
        remote_asr = transcription['provider'] != 'local'
        remote_diar = diar_config['provider'] != 'local'
        directory = self.store.root / job_id
        original = directory / ('original' + job['original_suffix'])
        wav = directory / 'working.wav'
        self.stage(job_id, 'normalizing', .05)
        self.run(job_id, [os.environ.get('MEETING_FFMPEG', 'ffmpeg'), '-nostdin', '-v', 'error', '-y',
                         '-protocol_whitelist', 'file,pipe', '-i', str(original), '-map', '0:a:0', '-vn', '-ac', '1', '-ar', '16000',
                         '-c:a', 'pcm_s16le', str(wav)], directory / 'normalize.log')
        with wave.open(str(wav)) as audio:
            duration = audio.getnframes() / audio.getframerate()
        if duration <= 0:
            raise ValueError('No audio samples found')
        self.store.update(job_id, duration=duration)
        self.stage(job_id, 'transcribing', .15)
        if job['profile'] == 'moss':
            asr_python = os.environ.get('MEETING_MOSS_PYTHON', os.environ.get('MEETING_DIAR_PYTHON', sys.executable))
            model_key = 'MEETING_MOSS_MODEL'
        elif job['profile'] == 'qwen-ko':
            asr_python = os.environ.get('MEETING_QWEN_PYTHON', sys.executable)
            model_key = 'MEETING_QWEN_MODEL'
        else:
            asr_python = os.environ.get('MEETING_ASR_PYTHON', sys.executable)
            model_key = 'MEETING_WHISPER_MODEL'
        model = transcription.get('model') or os.environ.get(model_key, '')
        if remote_asr:
            self.run(job_id, [sys.executable, str(WORKER.with_name('remote_worker.py')), '--stage', 'transcription',
                             '--audio', str(wav), '--output', str(directory / 'asr.json')], directory / 'asr.log',
                     input_data=json.dumps(transcription).encode())
        else:
            if not model:
                raise RuntimeError(f'Set {model_key} to the downloaded model directory')
            self.run(job_id, [asr_python, str(WORKER), 'asr', '--profile', job['profile'], '--model', model,
                             '--audio', str(wav), '--output', str(directory / 'asr.json')], directory / 'asr.log')
        asr = json.loads((directory / 'asr.json').read_text())
        if job['profile'] == 'moss' and not remote_asr:
            # Reject invalid joint timestamps before starting another model.
            joint_segments(asr, [], duration)
        self.store.update(job_id, raw_asr_text=asr['raw_asr_text'], timing_quality=asr['timing_quality'],
                          raw_structured_text=asr.get('raw_structured_text'), raw_joint_chunks=asr.get('chunks', []))
        # wait() has reaped the ASR process before the next GPU model can start.
        self.stage(job_id, 'diarizing', .65)
        diar_model = diar_config.get('model') or os.environ.get('MEETING_DIAR_MODEL', '')
        if remote_diar:
            self.run(job_id, [sys.executable, str(WORKER.with_name('remote_worker.py')), '--stage', 'diarization',
                             '--audio', str(wav), '--output', str(directory / 'diarization.json')], directory / 'diarization.log',
                     input_data=json.dumps(diar_config).encode())
        else:
            if not diar_model:
                raise RuntimeError('Set MEETING_DIAR_MODEL to the downloaded Nemotron directory')
            self.run(job_id, [os.environ.get('MEETING_DIAR_PYTHON', sys.executable), str(WORKER), 'diarize',
                             '--model', diar_model, '--audio', str(wav), '--output', str(directory / 'diarization.json')],
                     directory / 'diarization.log')
        diarization = json.loads((directory / 'diarization.json').read_text())
        turns = diarization['turns']
        self.stage(job_id, 'aligning', .95)
        joint = job['profile'] == 'moss' and not remote_asr and not remote_diar
        mapping_evidence = None
        if joint and len(asr.get('chunks', [])) > 1:
            from .longform_alignment import align_longform_joint
            segments, mapping_evidence = align_longform_joint(asr, turns, duration)
        else:
            segments = joint_segments(asr, turns, duration) if joint else align(asr, turns)
        speaker_ids = [s['speaker_id'] for s in segments] if joint else [t['speaker_id'] for t in turns] + [s['speaker_id'] for s in segments]
        speakers = {s: ('미지정' if s == 'unknown' else f'화자 {i + 1}')
                    for i, s in enumerate(dict.fromkeys(speaker_ids))}
        diarization['role'] = ('overlap_and_chunk_speaker_mapping' if mapping_evidence else 'overlap_review_only') if joint else 'speaker_assignment'
        diarization['speaker_namespace'] = 'remote' if remote_diar else 'nemotron'
        with self.lock:
            self.check(job_id)
            self.store.update(job_id, status='completed', progress=1.0, segments=segments,
                              speakers=speakers, diarization=[] if joint else turns, speaker_mapping_evidence=mapping_evidence,
                              overlap_review_activity={'speaker_namespace': 'nemotron', 'turns': turns} if joint else None,
                              models={'asr': asr['model'], 'diarization': diarization.get('model', 'nvidia/Nemotron-3-Diarization')},
                              inference={
                                  'asr': {k: v for k, v in asr.items() if k not in {'segments', 'raw_asr_text', 'raw_structured_text', 'chunks'}},
                                  'diarization': {k: v for k, v in diarization.items() if k != 'turns'},
                              })
