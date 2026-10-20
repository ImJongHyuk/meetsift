# Working on MeetSift

MeetSift is a Windows Electron/React desktop app with an Ubuntu/WSL2 Python backend.
The UI and default prompts are Korean. Do not advertise unverified language,
model, hardware or codec support.

## Install

Read README.md, docs/INSTALL.md and LICENSES.md before installing or packaging.

- Windows + NVIDIA: run scripts/setup-windows.ps1 -Mode Gpu -Check first, then
  scripts/setup-windows.ps1 -Mode Gpu -InstallSystemDependencies and
  scripts/start-windows.ps1.
- Ubuntu backend + NVIDIA: bash scripts/setup-backend.sh --gpu --system-deps.
- External audio providers: use Remote mode (Windows) or omit --gpu (Ubuntu),
  then configure both audio stages in the app.
- Do not install display drivers in WSL, replace system Python, silently select
  CPU inference, fabricate GPU results, or request an API key just to install.
- GPU success requires python3 scripts/doctor.py --mode gpu --smoke on actual
  compatible hardware. Preflight, mocks and dependency resolution are narrower checks.
- System dependencies may require sudo; WSL/driver installation can require a
  reboot. Report the exact missing prerequisite rather than retrying blindly.

## Source and verification

- desktop/: Electron main process, IPC, provider configuration and model catalog.
- web/: React UI; keep secrets outside the renderer.
- backend/meeting_backend/: API, job storage and isolated inference workers.
- extensions/chatgpt/: bundled adapter and pinned OpenAI SDK.
- scripts/: installation, diagnostics and publication guards.

Run npm ci, then npm run check. Run python3 -m unittest discover -s scripts/tests
for installer/diagnostic tests. On Linux, syntax-check each script: for script in scripts/*.sh; do bash -n "$script"; done.
Changes to inference also require a short authorized recording on real hardware;
inspect timestamps, speaker assignments and exports.

## License and privacy

Our independently authored code uses LICENSES/MIT.txt. The vendored OpenAI SDK
and copied credential-encryption.ts use the original noncommercial license.
Preserve upstream notices and mark modifications; do not label the full app MIT-only.
Run npm run check:licenses before packaging.

Never commit tokens, .env files, user data, recordings, model weights, Python
environments, local paths, work plans or execution reports. Installation creates
state only in ignored local directories. Run npm run check:public -- --history
before publishing and inspect any additional branch, tag or release asset.
