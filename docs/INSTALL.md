# Install and verify MeetSift

## Windows + WSL2

Supported setup path: Windows 11 x64 with WSL2 Ubuntu (Ubuntu 24.04 recommended),
Git, Node.js 22.12+ and Windows PowerShell 5.1+ or PowerShell 7.
Install WSL if needed with `wsl --install -d Ubuntu`, restart when requested,
and complete Ubuntu's first launch. These OS steps and GPU-driver installation
must finish before the project installer can run.

For GPU mode, use an NVIDIA GPU exposed to WSL and a Windows driver compatible
with CUDA 12.6 (the preflight conservatively requires driver 560+).
Do not install a Linux display driver or `cuda-drivers` inside WSL.
See [NVIDIA's WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).

From a fresh checkout:

```powershell
git clone https://github.com/ImJongHyuk/meetsift.git
cd meetsift
.\scripts\setup-windows.ps1 -Mode Gpu -InstallSystemDependencies
.\scripts\start-windows.ps1
```

If PowerShell blocks a reviewed local script, use a process-scoped invocation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-windows.ps1 -Mode Gpu -InstallSystemDependencies
```

`-InstallSystemDependencies` permits installing Ubuntu's Python, Git, curl,
FFmpeg and libsndfile through apt; sudo may ask for your Ubuntu password.
Omit it when these packages are already installed. uv uses a pinned official
installer if absent and manages Python 3.12 without changing system Python.
The setup does not install Node, WSL, GPU drivers or a system CUDA toolkit.

Backend code is copied into Ubuntu's user data directory, preserving isolated
environments, models and local state across setup reruns. The Windows checkout
contains only a local launcher configuration under ignored `.local-data/`.
The GPU installer covers transcription and diarization, not a local minutes LLM
server. Minutes require an interactive ChatGPT sign-in or another configured
provider after installation.

No API key is needed for installation, and the shared backend token is generated
locally, preserved on rerun and passed to Electron without printing it.

### External providers without a GPU

```powershell
.\scripts\setup-windows.ps1 -Mode Remote -InstallSystemDependencies
.\scripts\start-windows.ps1
```

This installs the API and FFmpeg, but no CUDA packages or model weights.
Set **both** audio stages to external providers in the app. The local API is
still needed for imports, playback and saved jobs. Configure minutes separately;
ChatGPT is included, subject to its account eligibility and SDK license.

### Preflight and diagnostics

Read-only GPU preflight; no package installation or downloads:

```powershell
.\scripts\setup-windows.ps1 -Mode Gpu -Check
```

GPU setup runs the following checks before reporting success:

1. Linux x64 platform, visible NVIDIA GPU and driver preflight.
2. Python API imports, FFmpeg and a local connection token.
3. CUDA availability and a tensor computation using the installed PyTorch.
4. Completed snapshots at the pinned model revisions.
5. Sequential MOSS and Nemotron inference on ten seconds of generated silence.

The final smoke check establishes execution, not transcription quality.
For a meaningful speech check, use a short recording you have permission to process
and inspect the resulting transcript in the app. The Linux doctor also accepts
`--audio recording.m4a`; it tests only the first ten seconds and does not print
transcript contents.

A successful API health check or dependency resolver run **does not establish GPU
inference**. On a machine without a visible GPU, GPU setup intentionally fails
before installing anything. Do not interpret that as a passed GPU test.

### Real-recording integration test

Use the [one-command GPU test](GPU-TEST.md) to install and exercise the complete
upload, transcription, diarization and export path with your own recording.
The guide includes a request you can give an AI agent on a fresh machine.

### Existing Windows ZIP

Keep the entire extracted ZIP together. In the cloned source checkout, pass
`-AppDirectory` with the extracted folder to reuse its desktop binary while
installing the backend:

```powershell
.\scripts\setup-windows.ps1 -Mode Gpu -InstallSystemDependencies -AppDirectory C:\Apps\MeetSift
.\scripts\start-windows.ps1
```

The ZIP includes the full ChatGPT integration and the mixed-license notices.
Models, Python, FFmpeg and GPU drivers are not bundled.

### Common failures

- **GPU not visible:** update the Windows NVIDIA driver and WSL; confirm
  `wsl -d Ubuntu -- nvidia-smi` works. Do not fall back silently to CPU inference.
- **Port in use:** stop the other backend or rerun setup with `-Port 18765`.
  The launcher authenticates before reusing a running backend.
- **Missing dependency / interrupted download:** fix the reported cause and rerun
  the same installer. Account files, tokens and recordings are not reset.
- **CUDA out of memory:** close other GPU applications or use external providers.
  There is no universal VRAM or recording-duration guarantee.
- **Blank desktop:** try `.\scripts\start-windows.ps1 -SoftwareRendering`.
  This affects Electron rendering, not audio-model CUDA computation.
- **Backend startup error:** inspect `.local-data/backend-stderr.log` in the Windows
  checkout. Do not publish logs or local configuration without review.

## Ubuntu backend

On x86-64 Ubuntu with a compatible NVIDIA driver:

```bash
git clone https://github.com/ImJongHyuk/meetsift.git
cd meetsift
bash scripts/setup-backend.sh --gpu --system-deps
bash scripts/run-backend.sh
```

For external providers, omit `--gpu`. The API binds only to loopback.
The launcher uses the project `.local-data/` directory and its persistent token.
Only one backend instance should own a data directory.

```bash
python3 scripts/doctor.py --mode gpu --smoke
python3 scripts/doctor.py --mode gpu --smoke --audio recording.m4a
```

Models are downloaded only during setup from revisions in
`scripts/model-catalog.json`. Inference is offline. MOSS executes custom Python
from its pinned snapshot (`trust_remote_code=True`); inspect that code before
changing revisions. Optional Whisper installation is enabled with `--whisper`.
`--skip-models` is a dependency-only developer option and never reports a
completed GPU installation.

The pinned CUDA wheels follow [PyTorch's official instructions](https://pytorch.org/get-started/previous-versions/).
Models, CUDA packages, FFmpeg and hosted services retain their own terms.
[License scope](../LICENSES.md).
