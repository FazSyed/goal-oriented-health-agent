import os
from cryptography.fernet import Fernet

KEY_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "secret.key")

class SecurityManager:
    """Manages Fernet symmetric encryption across the local backend."""

    def __init__(self, key_path: str = KEY_PATH):
        self.key_path = key_path
        self.cipher = Fernet(self._load_or_generate_key())

    def _load_or_generate_key(self) -> bytes:
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_path, "wb") as f:
                f.write(key)
            return key

    def encrypt_str(self, text: str) -> str:
        return self.cipher.encrypt(text.encode("utf-8")).decode("utf-8")

    def decrypt_str(self, encrypted_text: str) -> str:
        return self.cipher.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")