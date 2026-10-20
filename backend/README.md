# Local meeting audio backend

Python 3.12 FastAPI, one queue thread, one subprocess at a time. The original upload is copied byte-for-byte with a SHA-256 recorded; FFmpeg creates a separate 16 kHz mono PCM16 WAV without trimming, enhancement or shifting timestamps. With local providers, MOSS joint transcription/diarization exits before the separate Nemotron overlap-review stage starts, releasing its GPU memory. Whisper fallback also runs ASR and diarization sequentially. Each audio stage can instead use an external timestamped API or OpenRouter, with per-job credentials kept only in memory and subprocess stdin. Minutes generation remains in Electron. See [provider configuration](../docs/PROVIDERS.md).

## Ubuntu / Windows WSL2 with NVIDIA

Use Ubuntu under WSL2 with a Windows NVIDIA driver supporting CUDA 12.6. Verify `nvidia-smi` inside WSL2; do not install a Linux kernel/display driver inside WSL. Install Python 3.12, uv, `ffmpeg` and `libsndfile1` in your own development environment. A CPU/macOS machine can run the API and tests, but these inference workers currently require NVIDIA CUDA.

From the application root:

```bash
bash scripts/setup-backend.sh --gpu --system-deps
bash scripts/run-backend.sh
```

Setup installs environments, downloads pinned MOSS/Nemotron snapshots and runs CUDA plus model-worker smoke checks. It creates a persistent local connection token without printing it. See [installation and diagnostics](../docs/INSTALL.md) for prerequisites, verification levels, optional profiles and Windows automation.

For the Whisper alternative, pass `--whisper` during setup; it uses faster-whisper 1.2.1/CTranslate2 4.7.2. The optional Qwen backend profile uses `MEETING_INSTALL_QWEN=1` and `--qwen` with a separate qwen-asr 0.0.6/Transformers 4.57.6 environment; it is not exposed in the desktop UI. GPU driver compatibility depends on the host system.

Pre-existing cached models and environments are supported. Set absolute paths:

| Variable | Meaning |
| --- | --- |
| `MEETING_MOSS_PYTHON` | MOSS Python; defaults to `MEETING_DIAR_PYTHON` |
| `MEETING_MOSS_MODEL` | Cached MOSS-Transcribe-Diarize directory |
| `MEETING_ASR_PYTHON` | Python with faster-whisper / CUDA dependencies |
| `MEETING_DIAR_PYTHON` | Python with Transformers 5.19.0 and CUDA PyTorch |
| `MEETING_QWEN_PYTHON` | Optional separate Qwen Python |
| `MEETING_WHISPER_MODEL` | Cached faster-whisper-large-v3 directory |
| `MEETING_DIAR_MODEL` | Cached Nemotron-3-Diarization directory |
| `MEETING_QWEN_MODEL` | Optional cached Korean Qwen directory |
| `MEETING_API_TOKEN` | Shared capability token supplied by desktop main process |
| `MEETING_DATA_DIR` | Store directory; default `~/.meeting-notes` |
| `MEETING_FFMPEG` | FFmpeg executable; default `ffmpeg` |
| `MEETING_MAX_UPLOAD_BYTES` | Upload size limit; default 2 GiB |

Direct launch: from `backend/`, `.venv/bin/python -m meeting_backend --host 127.0.0.1 --port 8765`. The CLI accepts only loopback hosts. The launcher additionally locates NVIDIA shared libraries from the ASR environment. If the token is absent, the backend generates a persistent random token in `MEETING_DATA_DIR/api-token` with mode 0600. Keep data, models, environments and this token out of version control. One backend instance must own a given data directory.

## HTTP contract

`GET /health` is unauthenticated and contains `profiles` and `default_profile`. All other routes require `Authorization: Bearer <token>`. No CORS wildcard is enabled; desktop and Vite proxy requests. Original audio also accepts `?token=` for clients that cannot set an audio header, but the desktop protocol proxy should keep it out of renderer URLs.

- `GET /api/jobs` returns an array of job objects.
- `POST /api/jobs` accepts multipart `file` and `profile`; returns 201 and the queued job.
- `GET /api/jobs/{id}` returns a job including segments, speakers, rules, minutes and errors.
- `PATCH /api/jobs/{id}` accepts `title` (`name` alias), `rules`, `minutes`, `speakers: {speaker_id: displayName}`, and `segments: [{id, text?, speaker_id?}]` (`speaker` alias). Unknown segment/speaker IDs fail with 400. Text edits preserve original text and raw words.
- `POST /api/jobs/{id}/cancel` cancels queued or running work and terminates only that job's own subprocess group.
- `GET /api/jobs/{id}/audio` serves the unchanged original with byte range support.
- `GET /api/jobs/{id}/export?format=json|markdown` downloads timestamps, speaker labels, overlap/review flags and edited text. `md` is an alias. JSON also preserves raw ASR text, original segment text and words.

Jobs contain `id,title,name,filename,status,progress,profile,duration,created_at,updated_at,error,segments,speakers,rules,minutes,raw_asr_text,timing_quality`. Status is `queued`, `normalizing`, `transcribing`, `diarizing`, `aligning`, `completed`, `failed`, or `cancelled`. Progress is a stage estimate between 0 and 1, not measured completion within the model. Restarts mark interrupted jobs failed; reimport the original to run again. Each job has atomically saved JSON, untouched original audio, working WAV, raw stage JSON and stage logs. No resume/database migration system is included. For a failed or cancelled job, fix the reported environment/model error if needed, then import the original again; previous records remain available.

## Accuracy boundaries

The default `moss` profile produces text, anonymous speaker IDs and estimated segment timestamps jointly using float16, SDPA, greedy generation, batch 1 and at most 16,384 output tokens. For a single input chunk, MOSS speaker IDs are namespaced as `moss_S01` etc. and remain intact; Nemotron only adds overlap review flags. Recordings longer than 300 seconds use contiguous, non-overlapping chunks of at most 300 seconds. Segments touching the two seconds on either side of an internal cut receive `chunk_boundary` review flags; text is not heuristically merged. The last partial chunk is included, chunk-local timestamps are validated before global offsets are applied, and CUDA cache is released after each chunk. Raw text, source frame ranges, offsets and original local speaker IDs are stored for every chunk. A raw chunk JSON file is written before validation, so rejected model output is still available for diagnosis. To link speakers across chunks, aggregate overlap with Nemotron activity selects one one-to-one speaker-label permutation for each chunk; sentences are never individually reassigned. Unsupported or ambiguous mappings keep their chunk-specific ID and a review flag. Mapping evidence is exported for inspection. Nemotron anonymous IDs are stored under `overlap_review_activity` with a separate `nemotron` namespace and are never treated as MOSS speaker identities. MOSS segments that overlap each other are also flagged. Structured raw MOSS output and original segment text remain preserved after edits. Non-finite, reversed, negative or out-of-recording timestamps cause a clear failure rather than an invented correction. Hitting the output-token limit fails as potentially incomplete.

GPU memory use depends on input features, generation cache, model and recording duration. Chunking bounds each MOSS generation input; speaker matching and cut boundaries still require review. The whole-recording Nemotron pass allocates features proportional to duration. There is no fixed memory or recording-length guarantee.

The alternative `whisper-int8` uses explicit CTranslate2 `int8_float16`, Korean, greedy beam 1, temperature 0, previous-text conditioning off, VAD on and estimated word timestamps. `whisper-fp16` retains the same decoding at float16. These profiles align words to Nemotron activity and preserve multiple speaker candidates. Experimental `qwen-ko` uses fixed 25-second chunks without a forced aligner: coarse times and speaker assignments are inadequate for the main user workflow, so this profile is not advertised as a usable diarized-transcript option.

Native Nemotron supports up to eight anonymous speaker channels. File processing uses native offline mode: the installed Transformers implementation internally chunks the encoder with 340 frames plus 40 right-context frames, FIFO length 40 and cache update period 300. Features, embeddings and output arrays still grow with duration; memory is not constant. The worker does not provide a streaming interface. Overlap marking is review evidence, not source separation: overlapped words can still be missed. Speaker names are manual labels, not identified people. Edited text does not re-align model timestamps. All workers require explicit local model directories and run with Hugging Face offline mode enabled.

## Tests

```bash
uv pip install --python backend/.venv/bin/python -r backend/requirements-test.txt
cd backend
.venv/bin/python -m pytest -q
```

Tests cover MOSS joint speaker preservation, independent overlap evidence, strict timestamp validation, Whisper decoding parameters, simultaneous/adjacent speaker alignment, missing speakers, authentication, host validation, original-audio byte ranges, atomic persistence/reload, edits and exports, cancelled child isolation and FFmpeg normalization. Inference fixture tests are not GPU or ASR accuracy evidence.

JSON also retains `raw_joint_chunks` and `speaker_mapping_evidence` for multi-chunk recordings. Both exports include inference precision, decoding parameters, runtime versions and diarization mode. Model provenance stores the pinned `declared_revision`; `weights_verified` is false because configurable local weights have not been hashed against that revision. Override declarations for custom snapshots with `MEETING_MOSS_REVISION`, `MEETING_WHISPER_REVISION`, `MEETING_DIAR_REVISION`, or `MEETING_QWEN_REVISION`. A declaration is not proof of byte-identical model weights. FFmpeg input protocols are restricted to local files and pipes.
