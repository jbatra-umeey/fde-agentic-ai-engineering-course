import hashlib
import hmac
import json
import os
import re

from jev_core.models import DomainError, Principal


def load_identities():
    """Config maps SHA-256 hashes of high-entropy tokens to trusted identities."""
    raw = os.environ.get("JEV_IDENTITIES_JSON")
    if not raw:
        raise RuntimeError("JEV_IDENTITIES_JSON required; run scripts/dev_credentials.py")
    records = json.loads(raw)
    if not isinstance(records, dict) or not records:
        raise ValueError("Nonempty identity map required")
    result = {}
    for key, value in records.items():
        if not re.fullmatch(r"[a-f0-9]{64}", key):
            raise ValueError("Identity map keys must be SHA-256 hashes")
        result[key] = Principal.model_validate(value)
    return result


def authenticate(authorization, identities):
    if not authorization or not authorization.startswith("Bearer "):
        raise DomainError("unauthorized", 401)
    token = authorization[7:]
    if not 32 <= len(token) <= 256:
        raise DomainError("unauthorized", 401)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    for expected, principal in identities.items():
        if hmac.compare_digest(token_hash, expected):
            return principal
    raise DomainError("unauthorized", 401)
