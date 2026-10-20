"""Create a local connection token once; never print it or overwrite an account."""
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1] / ".local-data"
root.mkdir(mode=0o700, parents=True, exist_ok=True)
token = root / "api-token"
try:
    fd = os.open(token, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    if len(token.read_text().strip()) < 32:
        raise SystemExit("Existing local token is invalid; inspect it locally before replacing it.")
else:
    with os.fdopen(fd, "w") as stream:
        stream.write(secrets.token_urlsafe(32))
os.chmod(token, 0o600)
