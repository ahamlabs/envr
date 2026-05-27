"""CLI configuration helpers."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import platformdirs
import tomli_w


def _default_config_dir() -> Path:
    """Resolve config path, preferring ~/.envr and falling back to platformdirs."""
    try:
        return Path.home() / ".envr"
    except RuntimeError:
        return Path(platformdirs.user_config_dir("envr", appauthor=False))


CONFIG_DIR = _default_config_dir()
CONFIG_PATH = CONFIG_DIR / "config.toml"


def read_config() -> dict[str, Any]:
    """Read config from ~/.envr/config.toml if it exists."""
    if not CONFIG_PATH.exists():
        return {}
    return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def write_config(config: dict[str, Any]) -> None:
    """Persist config to ~/.envr/config.toml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(tomli_w.dumps(config), encoding="utf-8")


def set_server_url(server_url: str) -> None:
    """Set the server URL in config."""
    config = read_config()
    config["server"] = server_url.rstrip("/")
    write_config(config)


def get_server_url() -> str:
    """Return configured server URL or raise a runtime error."""
    server = read_config().get("server", "").strip()
    if not server:
        raise RuntimeError("Server URL is not configured. Run: envr config set server <URL>")
    return server.rstrip("/")
