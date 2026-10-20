# Security

Please report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/ImJongHyuk/meetsift/security/advisories/new).
Do not include real recordings, credentials or private configuration in a public issue.

The backend binds to loopback and authenticates job routes with a local token.
Do not expose it directly to a network. Provider keys and ChatGPT tokens belong
in the encrypted application store, never the renderer, source tree or job JSON.

Only run trusted local integration code. GPU setup downloads pinned model code;
MOSS requires custom Python from its model snapshot. Review changes to model
revisions, installer URLs and vendored SDK source before using them.
