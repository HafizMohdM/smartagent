"""
Credential encryption using Fernet symmetric encryption.
All service credentials (DB passwords, API keys, etc.) are encrypted
at rest and only decrypted when needed for active connections.
"""

from cryptography.fernet import Fernet, InvalidToken
from backend.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class CredentialEncryptor:
    """Encrypts and decrypts service credentials using Fernet."""

    def __init__(self, key: str | None = None):
        encryption_key = key or settings.APP_ENCRYPTION_KEY
        if not encryption_key:
            logger.warning(
                "No APP_ENCRYPTION_KEY set. Generating ephemeral key — "
                "credentials will NOT survive restarts."
            )
            encryption_key = Fernet.generate_key().decode()
        self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string and return base64-encoded ciphertext."""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a base64-encoded ciphertext and return plaintext."""
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            logger.error("Failed to decrypt credential — invalid token or wrong key.")
            raise ValueError("Decryption failed. The encryption key may have changed.")

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key."""
        return Fernet.generate_key().decode()

_encryptor = CredentialEncryptor()

def encrypt_password(password: str) -> str:
    """Helper to encrypt a service password."""
    return _encryptor.encrypt(password)

def decrypt_password(encrypted_password: str) -> str:
    """Helper to decrypt a service password."""
    return _encryptor.decrypt(encrypted_password)
