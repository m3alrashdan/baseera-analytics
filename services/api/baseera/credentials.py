"""Authenticated encryption for connector credentials.

Credentials never reach the database in clear text and are never returned through the API.
A deployment supplies keys through ``BASEERA_SECRET_KEY``; retired keys stay readable through
``BASEERA_SECRET_KEYS_RETIRED`` so a key can be rotated without a maintenance window.

Every ciphertext is bound to the tenant and connector that owns it, so a stored value cannot be
replayed against a different row even by someone who can write to the database.
"""

from __future__ import annotations

import base64
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .errors import AppError

KEY_BYTES = 32
NONCE_BYTES = 12
_KEY_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_DEVELOPMENT_ENVIRONMENTS = {"development", "test"}


class SecretsUnavailable(RuntimeError):
    """The deployment has not supplied a usable encryption key."""


def _decode_key(raw: str) -> bytes:
    padded = raw + "=" * (-len(raw) % 4)
    try:
        key = base64.urlsafe_b64decode(padded)
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise SecretsUnavailable("A secret key must be base64url encoded") from exc
    if len(key) != KEY_BYTES:
        raise SecretsUnavailable(f"A secret key must decode to exactly {KEY_BYTES} bytes")
    return key


def _parse_entry(entry: str) -> tuple[str, bytes]:
    key_id, separator, material = entry.partition(":")
    if not separator:
        raise SecretsUnavailable("A secret key must be written as '<key-id>:<base64url-key>'")
    key_id = key_id.strip().lower()
    if not _KEY_ID.match(key_id):
        raise SecretsUnavailable("A key id may only use lowercase letters, digits, '-' and '_'")
    return key_id, _decode_key(material.strip())


@dataclass(frozen=True, slots=True)
class SecretBox:
    """Encrypts and decrypts credential payloads for one deployment."""

    active_key_id: str
    keys: Mapping[str, bytes]

    @classmethod
    def from_environment(cls, environment: str) -> SecretBox | None:
        """Build a box from the process environment.

        Returns ``None`` only in development and test when no key is configured, so local work
        keeps running without credentials. Every other environment fails closed.
        """

        active = os.getenv("BASEERA_SECRET_KEY", "").strip()
        if not active:
            if environment in _DEVELOPMENT_ENVIRONMENTS:
                return None
            raise SecretsUnavailable(
                "BASEERA_SECRET_KEY is required outside development. "
                "Generate one with: python -m baseera.credentials"
            )
        active_id, active_key = _parse_entry(active)
        keys = {active_id: active_key}
        for entry in os.getenv("BASEERA_SECRET_KEYS_RETIRED", "").split(","):
            if not entry.strip():
                continue
            retired_id, retired_key = _parse_entry(entry.strip())
            if retired_id == active_id and retired_key != active_key:
                raise SecretsUnavailable(f"Key id '{retired_id}' is reused with different material")
            keys.setdefault(retired_id, retired_key)
        return cls(active_key_id=active_id, keys=keys)

    def encrypt(self, plaintext: bytes, *, context: str) -> str:
        """Return ``<key-id>.<nonce>.<ciphertext>`` bound to ``context``."""

        nonce = os.urandom(NONCE_BYTES)
        key = self.keys[self.active_key_id]
        sealed = AESGCM(key).encrypt(nonce, plaintext, context.encode("utf-8"))
        return ".".join(
            [
                self.active_key_id,
                base64.urlsafe_b64encode(nonce).decode("ascii").rstrip("="),
                base64.urlsafe_b64encode(sealed).decode("ascii").rstrip("="),
            ]
        )

    def decrypt(self, token: str, *, context: str) -> bytes:
        """Reverse :meth:`encrypt`, rejecting a value stored against a different context."""

        try:
            key_id, nonce_part, sealed_part = token.split(".")
        except ValueError as exc:
            raise AppError(
                500, "credential_unreadable", "The stored credential is malformed"
            ) from exc
        key = self.keys.get(key_id)
        if key is None:
            raise AppError(
                500,
                "credential_key_missing",
                f"The key '{key_id}' that encrypted this credential is not configured",
            )
        try:
            nonce = base64.urlsafe_b64decode(nonce_part + "=" * (-len(nonce_part) % 4))
            sealed = base64.urlsafe_b64decode(sealed_part + "=" * (-len(sealed_part) % 4))
            return AESGCM(key).decrypt(nonce, sealed, context.encode("utf-8"))
        except (InvalidTag, ValueError) as exc:
            raise AppError(
                500, "credential_unreadable", "The stored credential could not be decrypted"
            ) from exc

    def needs_rotation(self, token: str) -> bool:
        """True when ``token`` was sealed by a retired key and should be re-encrypted."""

        return token.split(".", 1)[0] != self.active_key_id


def credential_context(organization_id: str, connector_id: str) -> str:
    """Bind a ciphertext to the tenant and connector that owns it."""

    return f"baseera:connector-credentials:v1:{organization_id}:{connector_id}"


def generate_key(key_id: str = "v1") -> str:
    """Return a fresh ``<key-id>:<base64url-key>`` entry for BASEERA_SECRET_KEY."""

    material = base64.urlsafe_b64encode(os.urandom(KEY_BYTES)).decode("ascii").rstrip("=")
    return f"{key_id}:{material}"


if __name__ == "__main__":  # pragma: no cover - operator helper
    print(generate_key())
