"""Explicit opt-in model download; processing itself never contacts Hugging Face."""
import argparse
from pathlib import Path
from huggingface_hub import snapshot_download

p = argparse.ArgumentParser()
p.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[1] / 'models')
p.add_argument('--whisper', action='store_true', help='Download the alternative Whisper model')
p.add_argument('--qwen', action='store_true', help='Experimental profile; not exposed in the desktop UI')
a = p.parse_args()
models = [
    ('OpenMOSS-Team/MOSS-Transcribe-Diarize', '704aa4a9c304e8520be88901e0d1960158ef5b15'),
    ('nvidia/Nemotron-3-Diarization', 'f667ed73aee57d40cc39428eb768b4fd87a0a29e'),
]
if a.whisper:
    models.append(('Systran/faster-whisper-large-v3', 'edaa852ec7e145841d8ffdb056a99866b5f0a478'))
if a.qwen:
    models.append(('TeamUNIVA/qwen3_asr_1.7b_ko', '3e66f586033753589c3effeb2c8cbce46a1ddabb'))
# MOSS .py custom model files are required from the pinned snapshot.
for model, revision in models:
    snapshot_download(model, revision=revision, local_dir=a.directory / model.replace('/', '__'),
                      ignore_patterns=['*.nemo', '*.gguf', '*.gif', '*.mp4'])
