#!/usr/bin/env bash
# Ubuntu/WSL2. Installs only project environments; never GPU/display drivers.
set -euo pipefail
app_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$app_root/.local-tools:$HOME/.local/bin:/usr/lib/wsl/lib:$PATH"
mode=remote; check=0; system_deps=0; skip_models=0
for arg in "$@"; do
  case "$arg" in
    --gpu) mode=gpu ;;
    --check) check=1 ;;
    --system-deps) system_deps=1 ;;
    --skip-models) skip_models=1 ;;
    --whisper) export MEETING_INSTALL_WHISPER=1 ;;
    --help) echo 'Usage: setup-backend.sh [--gpu] [--check] [--system-deps] [--skip-models] [--whisper]'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done
# Reject unavailable GPUs before downloading packages or changing the system.
python3 "$app_root/scripts/doctor.py" --mode "$mode" --preflight
if [[ "$check" == 1 ]]; then exit 0; fi
if [[ "$system_deps" == 1 ]]; then
  sudo_cmd=()
  if [[ "$EUID" != 0 ]]; then sudo_cmd=(sudo); fi
  "${sudo_cmd[@]}" apt-get update
  "${sudo_cmd[@]}" apt-get install -y python3 git curl ffmpeg libsndfile1
fi
for tool in git curl ffmpeg; do
  command -v "$tool" >/dev/null || { echo "Missing $tool. Install system prerequisites or pass --system-deps." >&2; exit 1; }
done
if ! command -v uv >/dev/null; then
  installer="$(mktemp)"
  trap 'rm -f "$installer"' EXIT
  curl --fail --location --silent --show-error https://astral.sh/uv/0.12.19/install.sh -o "$installer"
  UV_UNMANAGED_INSTALL="$app_root/.local-tools" sh "$installer"
fi
uv python install 3.12
uv venv --allow-existing --python 3.12 "$app_root/backend/.venv"
uv pip install --python "$app_root/backend/.venv/bin/python" -r "$app_root/backend/requirements.txt"
"$app_root/backend/.venv/bin/python" "$app_root/scripts/init-local.py"
if [[ "$mode" == remote ]]; then
  python3 "$app_root/scripts/doctor.py" --mode remote
  echo 'Ready: API installed. Configure external audio providers in the app.'
  exit 0
fi
uv venv --allow-existing --python 3.12 "$app_root/backend/.venv-native"
uv pip install --python "$app_root/backend/.venv-native/bin/python" 'torch==2.11.0' 'torchaudio==2.11.0' --index-url https://download.pytorch.org/whl/cu126
uv pip install --python "$app_root/backend/.venv-native/bin/python" -r "$app_root/backend/requirements-gpu.txt"
download_args=()
if [[ "${MEETING_INSTALL_WHISPER:-0}" == 1 ]]; then
  uv venv --allow-existing --python 3.12 "$app_root/backend/.venv-asr"
  uv pip install --python "$app_root/backend/.venv-asr/bin/python" 'torch==2.11.0' --index-url https://download.pytorch.org/whl/cu126
  uv pip install --python "$app_root/backend/.venv-asr/bin/python" 'faster-whisper==1.2.1' 'ctranslate2==4.7.2' 'soundfile==0.13.1'
  download_args+=(--whisper)
fi
if [[ "${MEETING_INSTALL_QWEN:-0}" == 1 ]]; then
  uv venv --allow-existing --python 3.12 "$app_root/backend/.venv-qwen"
  uv pip install --python "$app_root/backend/.venv-qwen/bin/python" 'torch==2.11.0' --index-url https://download.pytorch.org/whl/cu126
  uv pip install --python "$app_root/backend/.venv-qwen/bin/python" 'qwen-asr==0.0.6' 'transformers==4.57.6' 'soundfile==0.13.1'
  download_args+=(--qwen)
fi
if [[ "$skip_models" == 1 ]]; then
  echo 'Dependencies installed; models and inference NOT verified. Complete the default GPU setup before use.'
  exit 0
fi
"$app_root/backend/.venv-native/bin/python" "$app_root/scripts/download-models.py" "${download_args[@]}"
python3 "$app_root/scripts/doctor.py" --mode gpu --smoke
echo 'Ready: CUDA computation and both default model workers passed.'
