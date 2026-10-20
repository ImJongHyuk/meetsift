import copy
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

TERMINAL = {'completed', 'failed', 'cancelled'}


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = threading.RLock()
        self.jobs = {}
        for path in self.root.glob('*/job.json'):
            job = json.loads(path.read_text())
            if job['status'] not in TERMINAL:
                job.update(status='failed', error='Service restarted during processing. Import the original again.')
            self.jobs[job['id']] = job
            self.save(job)

    def save(self, job):
        with self.lock:
            job = copy.deepcopy(job)
            job['updated_at'] = now()
            directory = self.root / job['id']
            directory.mkdir(exist_ok=True, mode=0o700)
            target = directory / 'job.json'
            temporary = target.with_suffix('.tmp')
            with temporary.open('w') as stream:
                json.dump(job, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(target)
            self.jobs[job['id']] = job
            return copy.deepcopy(job)

    def get(self, job_id):
        with self.lock:
            return copy.deepcopy(self.jobs[job_id])

    def update(self, job_id, **fields):
        with self.lock:
            job = self.get(job_id)
            job.update(fields)
            return self.save(job)

    def list(self):
        with self.lock:
            return copy.deepcopy(sorted(self.jobs.values(), key=lambda j: j['created_at'], reverse=True))


def public_job(job):
    job = copy.deepcopy(job)
    job['name'] = job['title']
    for segment in job['segments']:
        segment['speaker_name'] = job['speakers'].get(segment['speaker_id'], segment['speaker_id'])
    return job


def timestamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}'


def markdown(job):
    job = public_job(job)
    lines = [f"# {job['title']}", '', f"원본: {job['filename']}",
             f"모델: {job['profile']} · 시간 정보: {job.get('timing_quality', 'pending')}", '',
             '화자와 단어 시간은 모델 추정값입니다. 겹침 구간은 원본을 확인하세요.', '', '## 전사', '']
    for s in job['segments']:
        flags = ', '.join(s['review_flags'])
        label = f" [{flags}]" if flags else ''
        lines.append(f"[{timestamp(s['start'])}–{timestamp(s['end'])}] **{s['speaker_name']}**{label}: {s['text']}")
    if job.get('speaker_mapping_evidence'):
        lines.extend(['', '## 청크 화자 연결 근거', '', '```json',
                      json.dumps(job['speaker_mapping_evidence'], ensure_ascii=False, indent=2), '```'])
    if job.get('inference'):
        lines.extend(['', '## 처리 정보', '', '```json',
                      json.dumps(job['inference'], ensure_ascii=False, indent=2), '```'])
    if job.get('minutes'):
        lines.extend(['', '## 회의록', '', job['minutes']])
    if job.get('rules'):
        lines.extend(['', '## 작성 규칙', '', job['rules']])
    return '\n'.join(lines) + '\n'
