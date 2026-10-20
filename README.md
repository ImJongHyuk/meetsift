# MeetSift

**Turn recordings into clear meeting notes.**

A desktop workspace for transcribing recordings, reviewing who said what, and
turning the conversation into decisions and action items. Built for Korean
meetings, with your choice of local NVIDIA GPU, external servers, OpenRouter or
ChatGPT for the stages each provider supports.

> MeetSift's own code is **MIT**. The included OpenAI ChatGPT SDK and credential
> adapter have **noncommercial restrictions**. The complete app is not MIT-only.
> [License scope](LICENSES.md).

## What you can do

- Import Galaxy Voice Recorder **M4A**, common audio formats and videos with audio.
- Listen alongside timestamps; edit transcript text and speaker names.
- Configure transcription, diarization and minutes independently.
- Load writing rules from Markdown or text and export Markdown or JSON.

The interface and default prompts are Korean. Language support depends on the
selected model; multilingual UI and recognition quality are not guaranteed.

## Get started on Windows

Requires **Windows 11, WSL2 Ubuntu, Git and Node.js 22.12+**.
For local inference, install a compatible **NVIDIA Windows driver** first.
The installer checks GPU visibility before downloading CUDA packages or models.

```powershell
git clone https://github.com/ImJongHyuk/meetsift.git
cd meetsift
.\scripts\setup-windows.ps1 -Mode Gpu -InstallSystemDependencies
.\scripts\start-windows.ps1
```

Setup installs isolated Python environments, pinned MOSS and Nemotron models,
builds the desktop app and runs CUDA/model smoke checks. It downloads several GB
and may need your Ubuntu sudo password for system packages. It never installs GPU
drivers. Later launches use only the final command. Local GPU setup covers the
audio stages; minutes require ChatGPT sign-in or a configured model server.

Prefer a prebuilt desktop? Get the [Windows ZIP](https://github.com/ImJongHyuk/meetsift/releases/latest)
and follow the [existing ZIP setup](docs/INSTALL.md#existing-windows-zip).

**Using external audio providers?** Run setup with `-Mode Remote` instead.
This skips GPU packages and model downloads. In **모델·공급자 설정**, configure
both transcription and diarization before importing a recording.

[Installation, verification and troubleshooting](docs/INSTALL.md) ·
[Provider setup](docs/PROVIDERS.md) · [ChatGPT](docs/CHATGPT-EXTENSION.md)

Validate installation and the full audio pipeline with a real recording using
the [GPU integration test and agent request](docs/GPU-TEST.md).

## ChatGPT included

Choose **ChatGPT 연결** and sign in through OpenAI's official browser flow.
Eligible accounts can use their available ChatGPT plan models without a separate
Platform API key. Availability and limits are controlled by OpenAI.

ChatGPT receives the writing rules and reviewed transcript, including speaker
labels and timestamps, when you generate minutes. It does not receive the
original recording through this feature. SDK use must satisfy its
[noncommercial terms](extensions/chatgpt/vendor/siwc-local/LICENSE), including
the exclusion of business, employer and client operational use even without a fee.

## Files and data

M4A, MP3, WAV, AAC, FLAC, OGG/OGA, OPUS, WMA, AIF/AIFF, AMR and common video
containers are accepted. FFmpeg reads the first audio track; codec support depends
on the file and installed FFmpeg. Playback support depends on Chromium.

Recordings and results stay in the configured backend data directory when local
providers are used. External audio providers receive audio; external minutes
providers receive text. API keys and ChatGPT credentials are encrypted by the
desktop OS and are not exposed to the renderer or stored in job JSON.

Generated text and speaker labels need review. Model memory use varies with the
recording and hardware; chunking is not a guarantee for arbitrary recording lengths.

## Development

```sh
npm ci
npm run check
```

`npm run desktop` launches a built app; `npm run dev` runs the browser UI only.
The ChatGPT integration lives in this repository and builds automatically.
See [AGENTS.md](AGENTS.md) for agent-readable setup and checks,
[backend/README.md](backend/README.md) for API details and
[CONTRIBUTING.md](CONTRIBUTING.md) for contributions.
