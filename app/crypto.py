"""Fernet encryption at rest for secrets."""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class EncryptionError(Exception):
    pass


def _fernet() -> Fernet:
    key = get_settings().encryption_key
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        raise EncryptionError(f"Invalid ENCRYPTION_KEY: {exc}") from exc


def encrypt_value(plaintext: str) -> str:
    try:
        return _fernet().encrypt(plaintext.encode()).decode()
    except EncryptionError:
        raise
    except Exception as exc:
        raise EncryptionError(f"Encryption failed: {exc}") from exc


def decrypt_value(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise EncryptionError("Decryption failed: invalid or corrupted token") from exc
    except EncryptionError:
        raise
    except Exception as exc:
        raise EncryptionError(f"Decryption failed: {exc}") from exc
