# ChatGPT integration

This integration is included in MeetSift and built by `npm run build` at the
repository root. No separate checkout or extension installation is required.

`src/index.ts` is the independently authored MIT wrapper. OpenAI's SDK under
`vendor/siwc-local/` and the copied `src/credential-encryption.ts` retain the
DevKit Noncommercial License. This directory is **not MIT-only**.
See [license scope](LICENSES.md) and the [SDK license](vendor/siwc-local/LICENSE).

Build output is `dist-desktop/chatgpt/`. The Electron main process loads it
automatically and keeps credentials in the user's existing OS-encrypted store.
See [usage and data transfer](../../docs/CHATGPT-EXTENSION.md).
