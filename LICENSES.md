# License scope

MeetSift's independently authored application code and documentation are licensed
under the [MIT License](LICENSE). The root package metadata describes that grant;
it does not replace licenses of third-party software, model weights or services.

## MIT core

The core repository and desktop ZIP do not include the Sign-in with ChatGPT
DevKit, its Electron credential adapter or its runtime dependencies. Local models,
OpenRouter and OpenAI-compatible servers are available without the ChatGPT
extension. Model weights and the separately installed FFmpeg CLI are not included.

## Optional ChatGPT extension

[meetsift-chatgpt](https://github.com/ImJongHyuk/meetsift-chatgpt) is distributed
separately. It contains OpenAI's SDK and copied adapter under the
[Sign-in with ChatGPT DevKit Noncommercial License v1.0](https://github.com/openai/sign-in-with-chatgpt-devkit/blob/0a36fefeb913055c8c7a1a29b63d82b96b2e841a/LICENSE).
The MIT grant for MeetSift does not relicense those components or permit their
commercial use. Section 1 of the SDK license distinguishes independently authored
software using the SDK interface from modifications to the SDK itself.

The SDK license excludes business, employer and client operational use or
commercial advantage from its noncommercial definition, even when no fee is
charged. Commercial use of OpenAI's contribution requires a separate written
agreement with OpenAI. Its use/distribution restrictions do not satisfy section 6
of the [Open Source Definition](https://opensource.org/osd).

The extension is trusted local code, loaded only from an explicitly configured
absolute file path. MeetSift does not automatically install, download or bundle
it. See [extension installation](docs/CHATGPT-EXTENSION.md).

## Third-party components

React, Electron, npm/Python dependencies and their transitive dependencies keep
their respective licenses. Redistributed dependencies must retain required
copyright, license and notice files. In particular, preserve Apache notices where
applicable and Electron's `LICENSE.electron.txt` and `LICENSES.chromium.html`.
The latter includes notices for Chromium's bundled media components.

Downloaded model code and weights, CUDA packages and separately installed FFmpeg
builds have independent upstream terms. A MeetSift MIT grant does not relicense
them. Redistributing those components requires checking their exact licenses and
build options, rather than assuming they are MIT because MeetSift is MIT.

## Services and branding

Software licensing does not grant hosted inference access, account entitlement
or trademark rights. Each provider's service terms and model permissions apply.
[OpenAI's service documentation](https://developers.openai.com/siwc/token-sharing-open-source)
separately describes eligible ChatGPT plan usage for open-source and locally
hosted apps and directs paid or remotely hosted integrations to an interest form.
