#!/usr/bin/env bash
set -euo pipefail
app_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export MEETING_ASR_PYTHON="${MEETING_ASR_PYTHON:-$app_root/backend/.venv-asr/bin/python}"
export MEETING_DIAR_PYTHON="${MEETING_DIAR_PYTHON:-$app_root/backend/.venv-native/bin/python}"
export MEETING_MOSS_PYTHON="${MEETING_MOSS_PYTHON:-$MEETING_DIAR_PYTHON}"
export MEETING_MOSS_MODEL="${MEETING_MOSS_MODEL:-$app_root/models/OpenMOSS-Team__MOSS-Transcribe-Diarize}"
export MEETING_QWEN_PYTHON="${MEETING_QWEN_PYTHON:-$app_root/backend/.venv-qwen/bin/python}"
export MEETING_WHISPER_MODEL="${MEETING_WHISPER_MODEL:-$app_root/models/Systran__faster-whisper-large-v3}"
export MEETING_DIAR_MODEL="${MEETING_DIAR_MODEL:-$app_root/models/nvidia__Nemotron-3-Diarization}"
export MEETING_QWEN_MODEL="${MEETING_QWEN_MODEL:-$app_root/models/TeamUNIVA__qwen3_asr_1.7b_ko}"
# CTranslate2 resolves CUDA libraries from the ASR Python environment.
if [[ -x "$MEETING_ASR_PYTHON" ]]; then
  cuda_libs="$($MEETING_ASR_PYTHON -c 'import pathlib,site; print(":".join(str(p) for base in site.getsitepackages() for p in pathlib.Path(base).glob("nvidia/*/lib")))')"
  export LD_LIBRARY_PATH="$cuda_libs${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
cd "$app_root/backend"
exec .venv/bin/python -m meeting_backend "$@"
