"""Explicit opt-in download of immutable snapshots, including their licenses."""
import argparse
import json
from pathlib import Path
from huggingface_hub import snapshot_download

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--directory", type=Path, default=root / "models")
parser.add_argument("--whisper", action="store_true")
parser.add_argument("--qwen", action="store_true")
args = parser.parse_args()
catalog = json.loads((root / "scripts/model-catalog.json").read_text())
profiles = {"default"} | ({"whisper"} if args.whisper else set()) | ({"qwen"} if args.qwen else set())
for entry in catalog["models"]:
    if entry["profile"] not in profiles:
        continue
    destination = args.directory / entry["id"].replace("/", "__")
    snapshot_download(entry["id"], revision=entry["revision"], local_dir=destination,
                      ignore_patterns=["*.nemo", "*.gguf", "*.gif", "*.mp4"])
    # Mark only completed downloads. Runtime remains offline.
    (destination / ".meetsift-revision").write_text(entry["revision"] + "\n")
