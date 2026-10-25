"""Generate local teaching credentials; never print token values."""

import hashlib
import json
import os
import secrets
from pathlib import Path


def main():
    path = Path(".env")
    identities, lines = {}, ["JEV_DB=var/jev.sqlite", "JEV_PLANNER=fixture"]
    for role in ["operator", "reviewer", "reader"]:
        token = secrets.token_urlsafe(32)
        identities[hashlib.sha256(token.encode()).hexdigest()] = {
            "tenant": "demo",
            "subject": f"demo-{role}",
            "role": role,
        }
        lines.append(f"JEV_{role.upper()}_TOKEN={token}")
    lines.append("JEV_IDENTITIES_JSON='" + json.dumps(identities, separators=(",", ":")) + "'")
    # Exclusive create prevents accidental credential rotation or overwrite.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(
        "Created .env with fresh local identities. Load it as described in README; do not commit it."
    )


if __name__ == "__main__":
    main()
