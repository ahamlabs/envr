"""Ed25519 signing utilities for envr snapshots."""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


class SigningService:
    """Provides snapshot signing and key management."""

    def __init__(self, key_path: Path) -> None:
        self.key_path = key_path
        self._private_key = self._load_or_create_private_key()

    @property
    def public_key_hex(self) -> str:
        """Hex-encoded Ed25519 public key."""
        public_key = self._private_key.public_key()
        return public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()

    def sign(self, lock_sha256: str, tag: str, repo_url: str) -> str:
        """Sign the snapshot canonical message."""
        message = f"{lock_sha256}:{tag}:{repo_url}".encode("utf-8")
        return self._private_key.sign(message).hex()

    def _load_or_create_private_key(self) -> Ed25519PrivateKey:
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if self.key_path.exists():
            key_bytes = self.key_path.read_bytes()
            return Ed25519PrivateKey.from_private_bytes(key_bytes)

        private_key = Ed25519PrivateKey.generate()
        encoded = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.key_path.write_bytes(encoded)
        return private_key
