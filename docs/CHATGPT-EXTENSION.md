# ChatGPT integration

ChatGPT is included in MeetSift. Build or install the app normally; no separate
repository or extension path is needed. Choose **ChatGPT 연결**, complete the
official OpenAI browser sign-in, then choose ChatGPT as the minutes provider.

Eligible accounts use the models and plan allowance OpenAI makes available.
No Platform API key is entered for this provider. Service eligibility and quotas
are separate from software licensing.

## License

MeetSift's own interface and wrapper code remain MIT. The bundled OpenAI SDK and
copied credential adapter retain the
[DevKit Noncommercial License](../extensions/chatgpt/vendor/siwc-local/LICENSE).
The full app is not MIT-only. Personal learning, experimentation or development
must satisfy that license's noncommercial definition. Business, employer and
client operational use is excluded even without a fee.
See [complete scope](../LICENSES.md).

## Data and credentials

Generating minutes sends writing rules, reviewed transcript text, speaker
information, segment IDs, timestamps and review markers. This feature does not
send original audio. Credentials stay in Electron's main process, encrypted with
the OS safeStorage API, and are not returned to the renderer.

The existing application identity, user profile and encryption format are
preserved so previous connections and settings can be reused.

## Integration development

Source is in `extensions/chatgpt/`; `npm run build` compiles the SDK and adapter.
The default entry point is `dist-desktop/chatgpt/index.js`.
`MEETSIFT_CHATGPT_EXTENSION` can override it with an absolute path to trusted
local code. `MEETSIFT_DISABLE_CHATGPT=1` disables loading for development; it does
not remove bundled files or their license obligations.

The adapter API is version 1 and exports `createMeetSiftChatGPT(host)`.
The host supplies OS encryption, storage, browser opening and lifecycle methods.
Keep SDK modifications under their original license and preserve change notices.
