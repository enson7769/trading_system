import os
import getpass
from typing import Optional, Dict

class CredentialManager:
    def __init__(self):
        self._secrets: Dict[str, str] = {}

    def get_secret(
        self,
        key: str,
        prompt: str,
        env_var: Optional[str] = None,
        no_input: bool = False
    ) -> str:
        if key in self._secrets:
            return self._secrets[key]

        if env_var:
            from_env = os.getenv(env_var)
            if from_env:
                self._secrets[key] = from_env
                return from_env

        if not no_input:
            secret = getpass.getpass(prompt)
            if secret.strip():
                self._secrets[key] = secret.strip()
                return self._secrets[key]

        raise ValueError(f"Missing credential: {key}. Set env '{env_var}' or run without --no-input.")

    def clear_secret(self, key: str):
        self._secrets.pop(key, None)

    def clear_all(self):
        self._secrets.clear()