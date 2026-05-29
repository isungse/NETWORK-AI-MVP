from __future__ import annotations

import os
import re
from pathlib import Path


class CredentialMappingError(RuntimeError):
    pass


def credential_env_var(credential_ref: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", credential_ref).strip("_").upper()
    return f"NETWORK_AI_CREDENTIAL_{normalized}"


def resolve_credential_path(credential_ref: str) -> Path:
    env_var = credential_env_var(credential_ref)
    configured = os.environ.get(env_var)
    if not configured:
        raise CredentialMappingError(
            f"Credential mapping is not configured for credential_ref '{credential_ref}'. "
            f"Set {env_var} to the local encrypted credential file path."
        )
    return Path(configured)
