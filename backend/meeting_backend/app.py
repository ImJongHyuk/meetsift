import hashlib
import json
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .jobs import DEFAULT_PROFILE, JobManager, PROFILES
from .storage import Store, markdown, now, public_job
from .providers import validate_processing, public_processing


class SegmentEdit(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str
    text: str | None = Field(default=None, max_length=100000)
    speaker_id: str | None = None
    speaker: str | None = None


class JobEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str | None = Field(default=None, max_length=500)
    name: str | None = Field(default=None, max_length=500)
    segments: list[SegmentEdit] | None = None
    speakers: dict[str, str] | None = None
    rules: str | None = Field(default=None, max_length=100000)
    minutes: str | None = Field(default=None, max_length=1000000)


def create_app(data_dir=None, token=None, manager_factory=JobManager):
    store = Store(data_dir or os.environ.get('MEETING_DATA_DIR', str(Path.home() / '.meeting-notes')))
    token = token or os.environ.get('MEETING_API_TOKEN')
    if not token:
        token_path = store.root / 'api-token'
        if not token_path.exists():
            fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as stream:
                stream.write(secrets.token_urlsafe(32))
        token = token_path.read_text().strip()
    manager = manager_factory(store)

    @asynccontextmanager
    async def lifespan(app):
        manager.start()
        yield
        manager.close()

    app = FastAPI(title='Local Meeting Notes', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]'])
    app.state.store = store
    app.state.manager = manager

    @app.middleware('http')
    async def authenticate(request: Request, call_next):
        if request.url.path != '/health':
            credential = request.headers.get('authorization', '')
            supplied = credential.removeprefix('Bearer ') if credential.startswith('Bearer ') else ''
            if request.url.path.endswith('/audio') and not supplied:
                supplied = request.query_params.get('token', '')
            if not secrets.compare_digest(supplied.encode(), token.encode()):
                return Response('Unauthorized', status_code=401)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        return response

    def get_job(job_id):
        try:
            return store.get(job_id)
        except KeyError:
            raise HTTPException(404, 'Job not found')

    @app.get('/health')
    def health():
        return {'ok': True, 'profiles': ['moss', 'whisper-int8'], 'experimental_profiles': ['whisper-fp16', 'qwen-ko'], 'default_profile': DEFAULT_PROFILE}

    @app.get('/api/jobs')
    def list_jobs():
        return [public_job(job) for job in store.list()]

    @app.post('/api/jobs', status_code=201)
    async def import_audio(file: UploadFile = File(...), profile: str = Form(DEFAULT_PROFILE), processing_config: str | None = Form(default=None)):
        if profile not in PROFILES:
            raise HTTPException(400, f'Unknown profile: {profile}')
        config = None
        if processing_config is not None:
            try:
                if len(processing_config) > 64000:
                    raise ValueError('공급자 설정이 너무 큽니다.')
                config = validate_processing(json.loads(processing_config))
            except (ValueError, TypeError):
                raise HTTPException(400, '전사·화자 분리 공급자의 주소·모델·응답 형식을 확인하세요.') from None
        job_id = uuid.uuid4().hex
        filename = Path((file.filename or 'recording').replace('\\', '/')).name
        suffix = Path(filename).suffix.lower()
        if len(suffix) > 12 or not suffix.replace('.', '').isalnum():
            suffix = '.audio'
        directory = store.root / job_id
        directory.mkdir(mode=0o700)
        original = directory / ('original' + suffix)
        size = 0
        digest = hashlib.sha256()
        try:
            with original.open('wb') as target:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > int(os.environ.get('MEETING_MAX_UPLOAD_BYTES', str(2 * 1024**3))):
                        raise HTTPException(413, 'Recording exceeds upload limit')
                    digest.update(chunk)
                    target.write(chunk)
            if not size:
                raise HTTPException(400, 'Recording is empty')
        except BaseException:
            original.unlink(missing_ok=True)
            directory.rmdir()
            raise
        finally:
            await file.close()
        job = store.save(dict(id=job_id, title=Path(filename).stem, filename=filename, original_suffix=suffix,
                              original_sha256=digest.hexdigest(), original_bytes=size,
                              created_at=now(), status='queued', progress=0.0, profile=profile,
                              duration=None, error=None, segments=[], speakers={}, rules='', minutes='',
                              raw_asr_text='', timing_quality='pending',
                              **({'processing': public_processing(config)} if config else {})))
        if config is None:
            manager.submit(job_id)
        else:
            manager.submit(job_id, config)
        return public_job(job)

    @app.get('/api/jobs/{job_id}')
    def detail(job_id: str):
        return public_job(get_job(job_id))

    @app.patch('/api/jobs/{job_id}')
    def edit(job_id: str, patch: JobEdit):
        with store.lock:
            job = get_job(job_id)
            if patch.title is not None or patch.name is not None:
                job['title'] = patch.title if patch.title is not None else patch.name
            for field in ['rules', 'minutes']:
                if getattr(patch, field) is not None:
                    job[field] = getattr(patch, field)
            if patch.speakers is not None:
                if any(speaker not in job['speakers'] for speaker in patch.speakers):
                    raise HTTPException(400, 'Unknown speaker ID')
                if any(len(name) > 200 for name in patch.speakers.values()):
                    raise HTTPException(400, 'Speaker name too long')
                job['speakers'].update(patch.speakers)
            segments = {segment['id']: segment for segment in job['segments']}
            for change in patch.segments or []:
                if change.id not in segments:
                    raise HTTPException(400, 'Unknown segment ID')
                segment = segments[change.id]
                speaker = change.speaker_id if change.speaker_id is not None else change.speaker
                if speaker is not None:
                    if speaker not in job['speakers']:
                        raise HTTPException(400, 'Unknown speaker ID')
                    segment['speaker_id'] = segment['speaker'] = speaker
                if change.text is not None and change.text != segment['text']:
                    segment['text'] = change.text
                    if 'text_edited' not in segment['review_flags']:
                        segment['review_flags'].append('text_edited')
                # Original ASR words and original_text stay intact as editing evidence.
            return public_job(store.save(job))

    @app.post('/api/jobs/{job_id}/cancel')
    def cancel(job_id: str):
        get_job(job_id)
        return public_job(manager.cancel(job_id))

    @app.get('/api/jobs/{job_id}/audio')
    def audio(job_id: str):
        job = get_job(job_id)
        return FileResponse(store.root / job_id / ('original' + job['original_suffix']), filename=job['filename'],
                            content_disposition_type='inline',
                            media_type='audio/mp4' if job['original_suffix'] == '.m4a' else None)

    @app.get('/api/jobs/{job_id}/export')
    def export(job_id: str, format: str = 'json'):
        job = get_job(job_id)
        if format == 'json':
            return Response(json.dumps(public_job(job), ensure_ascii=False, indent=2), media_type='application/json',
                            headers={'Content-Disposition': f'attachment; filename="{job_id}.json"'})
        if format in {'markdown', 'md'}:
            return Response(markdown(job), media_type='text/markdown',
                            headers={'Content-Disposition': f'attachment; filename="{job_id}.md"'})
        raise HTTPException(400, 'format must be json or markdown')

    return app
