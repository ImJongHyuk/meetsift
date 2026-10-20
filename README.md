<p align="center">
  <img src="docs/assets/meetsift-icon.png" width="112" height="112" alt="MeetSift">
</p>

# MeetSift

English · [Korean](README.ko.md)

**From recording to meeting notes.**

Import a recording, review the transcript and speakers, then turn it into decisions and action items.

- Import Galaxy Voice Recorder **M4A**, common audio formats and videos with audio.
- Listen alongside timestamps, edit text and speaker names, and export Markdown or JSON.
- Choose transcription, diarization and minutes providers separately: local NVIDIA GPU, external servers, OpenRouter or ChatGPT, where supported.

The interface and default prompts are Korean. Recognition languages depend on the selected model.

## Windows quick start

Requires **Windows 11, WSL2 Ubuntu, Git and Node.js 22.12+**, plus a compatible NVIDIA Windows driver for local inference.

```powershell
git clone https://github.com/ImJongHyuk/meetsift.git
cd meetsift
.\scripts\setup-windows.ps1 -Mode Gpu -InstallSystemDependencies
.\scripts\start-windows.ps1
```

Setup installs isolated Python environments and pinned MOSS/Nemotron models, builds the app and checks CUDA. Allow several GB of downloads; Ubuntu may ask for your sudo password. GPU setup covers transcription and diarization. Connect ChatGPT or a model server to generate minutes.

For external audio providers, use `-Mode Remote` and configure both audio stages in provider settings. A [Windows ZIP](https://github.com/ImJongHyuk/meetsift/releases/latest) is also available.

[Installation & troubleshooting](docs/INSTALL.md) · [Providers](docs/PROVIDERS.md) · [ChatGPT](docs/CHATGPT-EXTENSION.md)

## Install and test with an AI agent

Paste this request into a terminal AI agent on another machine. **Replace the recording path and speaker count.**

```text
Clone https://github.com/ImJongHyuk/meetsift and install it following AGENTS.md.
Run the local GPU integration test on D:\Recordings\sample.m4a with 2 speakers; keep results locally.
If GPU support is unavailable or a test fails, explain the cause and next steps.
```

Requires an NVIDIA GPU and a short recording you are authorized to process. [Manual and Ubuntu commands](docs/GPU-TEST.md)

## Data & license

Local audio providers keep recordings and results on your machine. External audio providers receive audio; minutes providers receive text. ChatGPT receives writing rules and the reviewed transcript, including speaker labels and timestamps. Desktop credentials are encrypted by the OS. Review generated text and speaker labels before use.

MeetSift's own code is **MIT**. The included OpenAI ChatGPT SDK and credential adapter retain their **noncommercial license**; the full app is not MIT-only. The SDK terms also exclude employer and client operational use, even without a fee. See [license scope](LICENSES.md) and the [upstream terms](extensions/chatgpt/vendor/siwc-local/LICENSE).

## Development

```sh
npm ci
npm run check
```

`npm run desktop` opens the built app; `npm run dev` starts the browser UI only.

[Agent guide](AGENTS.md) · [Backend API](backend/README.md) · [Contributing](CONTRIBUTING.md)
