#!/usr/bin/env bash
# Run in Ubuntu/WSL2, after installing uv, Python 3.12 and FFmpeg.
set -euo pipefail
app_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v uv >/dev/null
command -v ffmpeg >/dev/null
uv venv --python 3.12 "$app_root/backend/.venv"
uv pip install --python "$app_root/backend/.venv/bin/python" -r "$app_root/backend/requirements.txt"
if [[ "${1:-}" != "--gpu" ]]; then
  echo 'API ready. Pass --gpu to also install isolated CUDA inference environments.'
  exit 0
fi
nvidia-smi
uv venv --python 3.12 "$app_root/backend/.venv-native"
uv pip install --python "$app_root/backend/.venv-native/bin/python" 'torch==2.11.0' --index-url https://download.pytorch.org/whl/cu126
uv pip install --python "$app_root/backend/.venv-native/bin/python" 'transformers==5.19.0' 'Jinja2>=3.1.6' soundfile librosa \
  'moss-transcribe-diarize @ git+https://github.com/OpenMOSS/MOSS-Transcribe-Diarize.git@e3bdd93f8ad58418e04659818efd5fd87a0bc486'
if [[ "${MEETING_INSTALL_WHISPER:-0}" == "1" ]]; then
uv venv --python 3.12 "$app_root/backend/.venv-asr"
uv pip install --python "$app_root/backend/.venv-asr/bin/python" 'torch==2.11.0' --index-url https://download.pytorch.org/whl/cu126
uv pip install --python "$app_root/backend/.venv-asr/bin/python" 'faster-whisper==1.2.1' 'ctranslate2==4.7.2' soundfile
fi
if [[ "${MEETING_INSTALL_QWEN:-0}" == "1" ]]; then
  uv venv --python 3.12 "$app_root/backend/.venv-qwen"
  uv pip install --python "$app_root/backend/.venv-qwen/bin/python" 'torch==2.11.0' --index-url https://download.pytorch.org/whl/cu126
  uv pip install --python "$app_root/backend/.venv-qwen/bin/python" 'qwen-asr==0.0.6' 'transformers==4.57.6' soundfile
fi
