# Contributing

Start with [installation](docs/INSTALL.md) and the [code map](AGENTS.md).
Keep changes focused and run `npm run check` plus the installer tests described
in AGENTS.md. Hardware-dependent changes need an actual GPU inference check;
state the limits of any checks you could not run.

Our own code and contributions to it use [MIT](LICENSES/MIT.txt). Changes to
vendored OpenAI code and its copied adapter must follow their original
noncommercial license and notice requirements. See [scope](LICENSES.md).

Do not include recordings, credentials, local configuration, model weights or
private logs in issues, patches or screenshots. Use synthetic fixtures.
Report sensitive vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/ImJongHyuk/meetsift/security/advisories/new).
