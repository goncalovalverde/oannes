"""Fernet-based encryption for sensitive SQLite columns.

The encryption key is read from OANNES_SECRET_KEY env var (32 url-safe base64 bytes).
If the key is absent, a random key is generated and persisted to DATA_DIR/.secret_key
so that a single-user local install works out of the box without manual setup.
"""
import os
import json
import logging
from pathlib import Path
from cryptography.fernet import Fernet
from sqlalchemy import types

logger = logging.getLogger(__name__)


def _load_or_create_key() -> bytes:
    env_key = os.getenv("OANNES_SECRET_KEY")
    if env_key:
        return env_key.encode()

    data_dir = Path(os.getenv("DATA_DIR", Path.home() / ".oannes"))
    data_dir.mkdir(parents=True, exist_ok=True)
    key_path = data_dir / ".secret_key"

    if key_path.exists():
        return key_path.read_bytes().strip()

    key = Fernet.generate_key()
    key_path.write_bytes(key)
    key_path.chmod(0o600)
    return key


_fernet: Fernet | None = None


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def encrypt_dict(data: dict) -> str:
    """Encrypt a dict to a base64-encoded ciphertext string."""
    plaintext = json.dumps(data).encode()
    return get_fernet().encrypt(plaintext).decode()


def decrypt_dict(ciphertext: str) -> dict:
    """Decrypt a ciphertext string back to a dict."""
    plaintext = get_fernet().decrypt(ciphertext.encode())
    return json.loads(plaintext)


class EncryptedJSON(types.TypeDecorator):
    """SQLAlchemy column type that transparently encrypts/decrypts a JSON dict.

    Usage::

        class Project(Base):
            config = Column(EncryptedJSON)
    """
    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_dict(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return decrypt_dict(value)
        except Exception:
            logger.warning(
                "EncryptedJSON: decryption failed for a config column — "
                "possible key rotation or data corruption. "
                "Falling back to plaintext JSON. Rotate or re-save the affected row's credentials."
            )
            # Graceful fallback: try plain JSON (pre-migration rows or rotated key)
            try:
                return json.loads(value)
            except Exception:
                return {}
