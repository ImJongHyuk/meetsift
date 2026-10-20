# Working on MeetSift

MeetSift is a Windows Electron/React app with an Ubuntu/WSL2 Python backend.
The UI and default prompts are Korean; language support depends on the model.
Keep changes focused and follow the conventions in nearby code.

## Code map

| Path | Responsibility |
| --- | --- |
| `desktop/` | Electron, IPC, encrypted credentials and provider catalog |
| `web/` | React UI |
| `backend/meeting_backend/` | API, job storage and isolated inference workers |
| `extensions/chatgpt/` | ChatGPT adapter and pinned OpenAI SDK |
| `scripts/` | Setup, diagnostics, integration tests and publication checks |

## Install and run

Read [installation](docs/INSTALL.md) and [license scope](LICENSES.md) first.
Run commands from the repository root.

```powershell
# Windows + WSL2 Ubuntu + NVIDIA
.\scripts\setup-windows.ps1 -Mode Gpu -Check
.\scripts\setup-windows.ps1 -Mode Gpu -InstallSystemDependencies
.\scripts\start-windows.ps1
```

Ubuntu backend: `bash scripts/setup-backend.sh --gpu --system-deps`.
For external audio providers, use Windows `-Mode Remote` or omit Ubuntu `--gpu`,
then configure both audio stages in the app.

- Check prerequisites before downloading models. Never install display drivers
  inside WSL or replace system Python.
- Report missing GPU, driver, WSL or sudo access with the next required action.
  Do not silently fall back to CPU/cloud or request an API key just to install.

## Verification

| Change | Check |
| --- | --- |
| TypeScript, UI, providers or packaging | `npm ci`, then `npm run check` |
| Python backend, setup or test harness | In Ubuntu/WSL: `backend/.venv/bin/python -m unittest discover -s scripts/tests -v` after backend setup |
| Shell scripts | In Ubuntu/WSL: `for script in scripts/*.sh; do bash -n "$script"; done` |
| Public docs or assets | `npm run check:licenses` and `npm run check:public -- --history`; check links and images |
| Inference or GPU installation | The real-recording GPU test below on compatible hardware |

The Python suite needs backend dependencies and FFmpeg to include the API
contract test. Report any skips. Unit tests, mocks and dependency resolution
are not proof that GPU inference works.

For an installation or GPU-test request, read [GPU-TEST.md](docs/GPU-TEST.md),
use the user's recording and expected speaker count, and run:

```powershell
.\scripts\test-gpu.ps1 -AudioPath 'D:\Recordings\sample.m4a' -MinSpeakers 2 -InstallSystemDependencies -KeepResults
```

On Ubuntu use `python3 scripts/test-gpu-recording.py --audio /path/to/sample.m4a --min-speakers 2 --install-system-deps --keep-results`.
These commands install first, then exercise the real API, FFmpeg, CUDA workers
and exports. Preserve the original recording. Keep results only in the ignored
local test directory. Stop on failure or timeout; report completed checks and
blockers without quoting private speech. Structural checks do not establish
recognition accuracy: inspect timestamps, speaker assignments and exports.

## Boundaries

- Keep API keys and ChatGPT credentials in the Electron main process, outside the
  renderer, job JSON and logs. External providers must remain an explicit choice.
- Never commit recordings, transcripts, tokens, local configuration, model weights,
  Python environments, personal paths, work plans or execution reports.
- Independently authored code is MIT. The vendored OpenAI SDK and copied
  `credential-encryption.ts` retain their original noncommercial license.
  Preserve upstream notices, mark modifications and never label the full app MIT-only.
- Run `npm run check:public -- --history` before publishing. Review any additional
  branch, tag or release asset. New binary assets need explicit hash review in
  `scripts/check-public-surface.mjs`; do not broaden the exception.
