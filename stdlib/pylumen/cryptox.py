"""Cryptography utilities for the Lumen standard library."""

import hashlib
import hmac as _hmac
import secrets
from typing import Union


def sha256(data: Union[str, bytes]) -> str:
    """Compute SHA-256 hash of data."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_file(filepath: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def hmac_sha256(key: Union[str, bytes], message: Union[str, bytes]) -> str:
    """Compute HMAC-SHA256."""
    if isinstance(key, str):
        key = key.encode("utf-8")
    if isinstance(message, str):
        message = message.encode("utf-8")
    return _hmac.new(key, message, hashlib.sha256).hexdigest()


def lhash(data: Union[str, bytes], algorithm: str = "sha256") -> str:
    """Hash data with specified algorithm."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.new(algorithm, data).hexdigest()


def lverify_hmac(key: Union[str, bytes], message: Union[str, bytes], expected: str) -> bool:
    """Verify HMAC-SHA256 against expected value."""
    computed = hmac_sha256(key, message)
    return secrets.compare_digest(computed, expected)


def xor_cipher(data: Union[str, bytes], key: Union[str, bytes]) -> bytes:
    """XOR cipher encryption. Returns bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if isinstance(key, str):
        key = key.encode("utf-8")
    if len(key) == 0:
        raise ValueError("key must not be empty")
    key_repeated = (key * ((len(data) // len(key)) + 1))[:len(data)]
    return bytes(d ^ k for d, k in zip(data, key_repeated))


def xor_decrypt(ciphertext: bytes, key: Union[str, bytes]) -> str:
    """XOR cipher decryption. Returns string."""
    result = xor_cipher(ciphertext, key)
    return result.decode("utf-8", errors="replace")


def generate_key(length: int = 32) -> bytes:
    """Generate a random key."""
    return secrets.token_bytes(length)


def generate_nonce(length: int = 16) -> bytes:
    """Generate a random nonce."""
    return secrets.token_bytes(length)


# --- XOR cipher demo ---
def xor_demo() -> dict:
    """Demonstrate XOR cipher with example."""
    plaintext = "Hello, Lumen!"
    key = "secret"
    encrypted = xor_cipher(plaintext, key)
    decrypted = xor_decrypt(encrypted, key)
    return {
        "plaintext": plaintext,
        "key": key,
        "encrypted_hex": encrypted.hex(),
        "decrypted": decrypted,
        "success": decrypted == plaintext,
    }
