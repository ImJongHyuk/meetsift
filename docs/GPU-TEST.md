# Verify a real recording on a GPU

This opt-in test installs MeetSift's GPU dependencies and pinned models, then
processes a recording you supply through the real upload API, job queue, FFmpeg,
MOSS transcription, Nemotron diarization and JSON/Markdown exports. It uses an
in-process ASGI client, so no desktop interaction, listening port or background
service is needed for the test itself. Model workers are real CUDA subprocesses.

Use a clear 30–120 second recording you are authorized to process. A two-speaker
conversation is recommended. The **entire file** is processed, not a ten-second
crop. No sample recording is bundled or downloaded, and audio is not sent to
ChatGPT, OpenRouter or another inference server.

## Windows + WSL2

First prepare the [OS prerequisites](INSTALL.md): Windows 11 x64, WSL2 Ubuntu,
Git, Node.js 22.12+ and a compatible NVIDIA Windows driver. From the checkout:

```powershell
.\scripts\test-gpu.ps1 -AudioPath 'D:\Recordings\sample.m4a' -MinSpeakers 2 -InstallSystemDependencies -KeepResults
```

If execution policy blocks a reviewed local script, use
`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-gpu.ps1`
with the same arguments. This changes policy only for that process.

This runs the existing Windows GPU installer, including the desktop build, and
then the recording test in its WSL environment. After installation and source
synchronization, use `-SkipSetup` to rerun only the test. `-Distribution` selects
the Ubuntu distribution for installation. The job timeout defaults to 1800 seconds;
change it with `-TimeoutSeconds` for slower hardware or longer recordings.

## Ubuntu

```bash
python3 scripts/test-gpu-recording.py --audio '/path/to/sample.m4a' --min-speakers 2 --install-system-deps --keep-results
```

The command runs `setup-backend.sh --gpu`, then switches to the installed API
Python environment automatically. Use `--skip-setup` for an existing installation,
and `--timeout 3600` to change the job timeout. Installation/download time is not
part of this timeout. Omit the system-dependency flag if apt prerequisites are
already installed. sudo may require a human-entered password.

## What passes

- A visible compatible GPU, CUDA computation and the pinned model snapshots.
- An authenticated API upload and completed default local pipeline; unauthenticated
  job access must be rejected.
- Nonempty transcript and diarization activity, valid timestamps and mapped
  speaker labels. `--min-speakers 2` requires at least two transcript speaker IDs;
  use 1 for a recording known to contain only one speaker.
- The original upload/playback bytes and input file retain their SHA-256.
- JSON and Markdown exports contain the completed transcript.

Exit code **0** means these checks passed. Missing GPU, model failure, empty
output, too few speakers, invalid times or timeout return a failure. A timeout
or Ctrl+C cancels only this test's job. A missing GPU never becomes a successful
skip or an automatic CPU/cloud fallback.

These are execution and structural checks, **not WER/DER or semantic accuracy
scores**. Compare the retained transcript, timestamps and speaker assignments
with the recording before accepting recognition quality. MOSS owns transcript
speaker labels; Nemotron activity has its separate speaker namespace.

## Private results

The test uses a separate store and an ephemeral token; it does not connect to an
existing backend, change provider settings or use your saved meetings. Temporary
audio, transcripts and logs are removed by default, including on failure.

`--keep-results` / `-KeepResults` retains them under the backend checkout's ignored
`.local-data/gpu-tests/<run-id>/`. This includes the original upload, worker logs,
`transcript.json`, `transcript.md` and `summary.json` on success. On Windows this
directory is in the configured **WSL backend source**; locate it through the local
`.local-data/windows.json`. Never commit or attach these files without review.
The command prints stage names and counts, not transcript contents or tokens.

## Ask an AI agent

Open a terminal agent such as Codex in an empty development directory and give it
the following request, replacing the recording path and expected speaker count:

```text
Clone https://github.com/ImJongHyuk/meetsift and read AGENTS.md, LICENSES.md,
docs/INSTALL.md and docs/GPU-TEST.md. Install it on this machine and run the
real-recording GPU integration test with D:\Recordings\sample.m4a, expecting
at least 2 speakers. I authorize local processing of this recording.
Use the provided one-command test, keep results locally for inspection, and
preserve the original recording. Do not use cloud inference or commit recordings,
transcripts, logs, tokens or local configuration. If a GPU/driver/WSL prerequisite
is missing, report the exact blocker and required next command; do not claim a
pass from CPU tests or mocks. Summarize checks and counts without quoting speech.
```

An agent opened in an existing checkout can omit the clone instruction. It should
check prerequisites first, run the platform command above, inspect the exit code
and local summary, and distinguish a passed integration test from manual accuracy
review. OS installation/reboots and interactive sudo prompts may require your
participation. No ChatGPT sign-in or inference API key is needed for this test.
