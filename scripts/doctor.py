"""Read-only installation checks; --smoke also runs local model inference."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[1]


def run(command, **kwargs):
    result = subprocess.run([str(item) for item in command], capture_output=True, text=True,
                            timeout=kwargs.pop("timeout", 120), **kwargs)
    if result.returncode:
        # Do not include arbitrary environment values or model output in diagnostics.
        raise RuntimeError("Command failed: " + Path(str(command[0])).name +
                           ". Run it locally for details; check dependencies, drivers and available memory.")
    return result.stdout.strip()


def preflight(mode):
    if platform.system() != "Linux" or platform.machine() not in ("x86_64", "AMD64"):
        raise RuntimeError("Use x86-64 Ubuntu or Ubuntu under WSL2 for the backend.")
    if mode == "gpu":
        executable = shutil.which("nvidia-smi")
        if not executable and Path("/usr/lib/wsl/lib/nvidia-smi").is_file():
            executable = "/usr/lib/wsl/lib/nvidia-smi"
        if not executable:
            raise RuntimeError("NVIDIA GPU not visible. Install/update the host driver and WSL2, then retry. Do not install a Linux display driver in WSL.")
        drivers = run([executable, "--query-gpu=driver_version", "--format=csv,noheader"])
        if not drivers or any(int(line.split(".")[0]) < 560 for line in drivers.splitlines()):
            raise RuntimeError("The pinned CUDA 12.6 runtime requires a compatible NVIDIA driver (560 or newer).")


def check_models():
    catalog = json.loads((ROOT / "scripts/model-catalog.json").read_text())
    directories = []
    for entry in catalog["models"]:
        if entry["profile"] != "default":
            continue
        directory = ROOT / "models" / entry["id"].replace("/", "__")
        marker = directory / ".meetsift-revision"
        if not marker.is_file() or marker.read_text().strip() != entry["revision"]:
            raise RuntimeError("Pinned model download is incomplete. Re-run GPU setup.")
        if not (directory / "config.json").is_file() or not list(directory.glob("*.safetensors")):
            raise RuntimeError("Model configuration or weights are missing. Re-run GPU setup.")
        directories.append(directory)
    return directories


def smoke(audio, directories):
    worker = ROOT / "backend/meeting_backend/worker.py"
    python = ROOT / "backend/.venv-native/bin/python"
    with tempfile.TemporaryDirectory(prefix="meetsift-doctor-") as name:
        temporary = Path(name)
        normalized = temporary / "audio.wav"
        if audio:
            run(["ffmpeg", "-nostdin", "-v", "error", "-i", audio, "-t", "10",
                 "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", normalized])
        else:
            with wave.open(str(normalized), "wb") as output:
                output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                output.writeframes(bytes(16000 * 2 * 10))
        for stage, model in zip(("asr", "diarize"), directories):
            output = temporary / (stage + ".json")
            run([python, worker, stage, "--profile", "moss", "--audio", normalized,
                 "--model", model, "--output", output], timeout=900, env={**os.environ, "HF_HUB_OFFLINE": "1"})
            result = json.loads(output.read_text())
            if ("segments" if stage == "asr" else "turns") not in result:
                raise RuntimeError("Model worker returned an invalid result.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("remote", "gpu"), default="gpu")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--audio", type=Path, help="Optional short recording for the inference smoke test")
    args = parser.parse_args()
    try:
        preflight(args.mode)
        result = {"preflight": True, "mode": args.mode}
        if not args.preflight:
            if not shutil.which("ffmpeg"):
                raise RuntimeError("FFmpeg is missing. Install system prerequisites.")
            python = ROOT / "backend/.venv/bin/python"
            run([python, "-c", "import fastapi,uvicorn,multipart,httpx"])
            token = ROOT / ".local-data/api-token"
            if not token.is_file() or len(token.read_text().strip()) < 32:
                raise RuntimeError("Local connection token is missing. Re-run setup.")
            result["api_dependencies"] = True
            if args.mode == "gpu":
                native = ROOT / "backend/.venv-native/bin/python"
                run([native, "-c", "import torch,torchaudio,transformers,soundfile,moss_transcribe_diarize; "
                     "assert torch.cuda.is_available(), 'CUDA unavailable'; "
                     "x=torch.ones((8,8),device='cuda'); assert torch.isfinite(x@x).all(); torch.cuda.synchronize()"])
                result["cuda_compute"] = True
                directories = check_models()
                result["model_snapshots"] = True
                if args.smoke:
                    smoke(args.audio, directories)
                    result["model_inference"] = True
        print(json.dumps(result))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"ok": False, "error": str(error)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
