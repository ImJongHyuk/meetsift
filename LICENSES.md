# Licenses

## MeetSift code and assets: MIT

MeetSift's independently authored code, documentation and artwork use the
[MIT License](LICENSES/MIT.txt). This includes the ChatGPT interface,
`extensions/chatgpt/src/index.ts` and build scripts. Preserve the copyright and permission
notice when redistributing that code. The exceptions below are not relicensed.

## OpenAI components: noncommercial

The full desktop app includes these OpenAI-authored components:

| Component | License |
| --- | --- |
| `extensions/chatgpt/vendor/siwc-local/` | [Sign-in with ChatGPT DevKit Noncommercial License v1.0](extensions/chatgpt/vendor/siwc-local/LICENSE) |
| `extensions/chatgpt/src/credential-encryption.ts` | The same noncommercial license; copied from the DevKit Electron example |

The SDK source is pinned to
[`0a36fefeb913055c8c7a1a29b63d82b96b2e841a`](https://github.com/openai/sign-in-with-chatgpt-devkit/tree/0a36fefeb913055c8c7a1a29b63d82b96b2e841a).
Its source, license, provenance and third-party notices are retained. The copied
adapter has a source/change notice. Changes to OpenAI's code must retain its
license and be marked as required by section 4.

Section 1 excludes independently authored software merely using the SDK interface
from the definition of a Modified Work. This permits the separate MIT grant for
MeetSift's own code; it does not expand rights in OpenAI's contribution.

The SDK permits only its defined Noncommercial Purposes: personal learning,
experimentation or development without an intended or reasonably anticipated
commercial application. Business, employer or client operational use or commercial
advantage is excluded even when no fee is charged. Commercial use of OpenAI's
contribution requires a separate written agreement with OpenAI.

**The complete repository and desktop ZIP are a mixed-license distribution, not
an MIT-only or commercially unrestricted distribution.** Disabling ChatGPT in
the UI does not remove the bundled SDK or change its terms. The noncommercial
components do not meet section 6 of the [Open Source Definition](https://opensource.org/osd).

## Other software, models and services

npm and Python dependencies retain their own licenses. Preserve required notices,
including Electron's `LICENSE.electron.txt` and `LICENSES.chromium.html`. The SDK's
[third-party notices](extensions/chatgpt/vendor/siwc-local/THIRD_PARTY_NOTICES.md)
also accompany the distribution.

Model weights, model custom code, CUDA packages and separately installed FFmpeg
have independent upstream terms. They are downloaded during explicit GPU setup,
not bundled in the desktop ZIP. Check their exact licenses/build options before
redistribution; MeetSift's MIT grant does not relicense them.

Software licenses do not grant service access, account eligibility, plan usage
or trademark rights. Provider terms apply separately; see the
[official ChatGPT integration documentation](https://developers.openai.com/siwc/token-sharing-open-source).
