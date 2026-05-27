"""Command helpers shared by envr CLI commands."""

from __future__ import annotations

import hashlib
import subprocess
from typing import Any

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def sha256_text(content: str) -> str:
    """Compute SHA256 hex digest for text content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_repo_url() -> str:
    """Try to resolve git origin URL from the current directory."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def post_env(server_url: str, tag: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Push a snapshot to the server."""
    url = f"{server_url}/envs/{tag}"
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, json=payload)
    response.raise_for_status()
    return response.json()


def get_env(server_url: str, tag: str) -> dict[str, Any]:
    """Fetch a snapshot from the server."""
    url = f"{server_url}/envs/{tag}"
    with httpx.Client(timeout=30.0) as client:
        response = client.get(url)
    response.raise_for_status()
    return response.json()


def list_envs(server_url: str, prefix: str = "") -> dict[str, Any]:
    """List snapshot metadata from the server."""
    params = {"prefix": prefix} if prefix else None
    with httpx.Client(timeout=30.0) as client:
        response = client.get(f"{server_url}/envs", params=params)
    response.raise_for_status()
    return response.json()


def verify_signature(
    *,
    public_key_hex: str,
    signature_hex: str,
    lock_sha256: str,
    tag: str,
    repo_url: str,
) -> None:
    """Verify an Ed25519 signature for the canonical snapshot message."""
    public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
    signature = bytes.fromhex(signature_hex)
    message = f"{lock_sha256}:{tag}:{repo_url}".encode("utf-8")
    public_key.verify(signature, message)


def run_uv_sync(*, frozen: bool) -> None:
    """Run `uv sync` with optional `--frozen` mode."""
    command = ["uv", "sync"]
    if frozen:
        command.append("--frozen")
    subprocess.run(command, check=True)
