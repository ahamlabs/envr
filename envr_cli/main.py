"""Typer-based CLI for envr snapshot workflows."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

import httpx
import typer
from cryptography.exceptions import InvalidSignature
from rich.console import Console
from rich.table import Table

from envr_cli.commands import (
    get_env,
    get_repo_url,
    list_envs,
    post_env,
    run_uv_sync,
    sha256_text,
    verify_signature,
)
from envr_cli.config import get_server_url, set_server_url
from envr_cli.manifest import read_manifest, write_manifest

app = typer.Typer(help="Share signed, reproducible uv.lock snapshots.")
config_app = typer.Typer(help="Configuration commands.")
set_app = typer.Typer(help="Set configuration values.")
config_app.add_typer(set_app, name="set")
app.add_typer(config_app, name="config")
console = Console()


@set_app.command("server")
def config_set_server(server_url: str) -> None:
    """Set the remote envr server URL."""
    set_server_url(server_url)
    console.print(f"[green]Configured envr server:[/green] {server_url.rstrip('/')}")


@app.command()
def push(tag: str, desc: str = typer.Option("", "--desc", help="Snapshot description.")) -> None:
    """Push local uv.lock to the configured server under TAG."""
    lock_path = Path.cwd() / "uv.lock"
    if not lock_path.exists():
        console.print("[red]uv.lock not found in current directory.[/red]")
        raise typer.Exit(code=1)

    try:
        server = get_server_url()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    lock_content = lock_path.read_text(encoding="utf-8")
    repo_url = get_repo_url()
    payload = {
        "lock_content": lock_content,
        "python_version": platform.python_version(),
        "description": desc,
        "repo_url": repo_url,
    }

    try:
        response = post_env(server, tag, payload)
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]Server rejected push:[/red] {exc.response.status_code} {exc.response.text}")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        console.print(f"[red]Failed to reach server:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    local_sha = sha256_text(lock_content)
    if local_sha != response["lock_sha256"]:
        console.print("[red]SHA mismatch between local uv.lock and server response.[/red]")
        raise typer.Exit(code=1)

    manifest = {
        "server": server,
        "tag": tag,
        "lock_sha256": response["lock_sha256"],
        "signature": response["signature"],
        "server_public_key": response["public_key"],
        "created": response["created_at"],
        "python": response["python_version"],
        "description": response["description"],
        "repo_url": response["repo_url"],
    }
    write_manifest(manifest)
    console.print(f"[green]Pushed snapshot:[/green] {tag}")
    console.print("[yellow]Next:[/yellow] git add .envr")


@app.command()
def pull(tag: str, apply: bool = typer.Option(False, "--apply", help="Run `uv sync` after writing uv.lock.")) -> None:
    """Pull snapshot TAG and write uv.lock."""
    try:
        server = get_server_url()
        response = get_env(server, tag)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]Pull failed:[/red] {exc.response.status_code} {exc.response.text}")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        console.print(f"[red]Failed to reach server:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    lock_content = response["lock_content"]
    computed_sha = sha256_text(lock_content)
    if computed_sha != response["lock_sha256"]:
        console.print("[red]Server lock content hash mismatch.[/red]")
        raise typer.Exit(code=1)

    manifest = read_manifest()
    if manifest:
        try:
            verify_signature(
                public_key_hex=manifest["server_public_key"],
                signature_hex=response["signature"],
                lock_sha256=response["lock_sha256"],
                tag=tag,
                repo_url=response.get("repo_url", ""),
            )
        except (KeyError, ValueError, InvalidSignature) as exc:
            console.print(f"[red]Signature verification failed:[/red] {exc}")
            raise typer.Exit(code=1) from exc

    Path("uv.lock").write_text(lock_content, encoding="utf-8")
    console.print(f"[green]Wrote uv.lock from tag:[/green] {tag}")

    if apply:
        try:
            run_uv_sync(frozen=False)
            console.print("[green]Applied environment with `uv sync`.[/green]")
        except (OSError, subprocess.CalledProcessError) as exc:
            console.print(f"[red]Failed to run uv sync:[/red] {exc}")
            raise typer.Exit(code=1) from exc


@app.command()
def sync() -> None:
    """Sync environment from .envr manifest and enforce signature verification."""
    manifest = read_manifest()
    if not manifest:
        console.print("[red].envr manifest not found in current directory.[/red]")
        raise typer.Exit(code=1)

    required_fields = {"server", "tag", "lock_sha256", "signature", "server_public_key", "repo_url"}
    missing = sorted(required_fields - set(manifest))
    if missing:
        console.print(f"[red]Manifest missing fields:[/red] {', '.join(missing)}")
        raise typer.Exit(code=1)

    try:
        response = get_env(manifest["server"], manifest["tag"])
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]Sync pull failed:[/red] {exc.response.status_code} {exc.response.text}")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        console.print(f"[red]Failed to reach server:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    lock_content = response["lock_content"]
    computed_sha = sha256_text(lock_content)
    if computed_sha != manifest["lock_sha256"] or response["lock_sha256"] != manifest["lock_sha256"]:
        console.print("[red]Snapshot hash mismatch with manifest.[/red]")
        raise typer.Exit(code=1)

    if response["signature"] != manifest["signature"]:
        console.print("[red]Snapshot signature mismatch with manifest.[/red]")
        raise typer.Exit(code=1)

    try:
        verify_signature(
            public_key_hex=manifest["server_public_key"],
            signature_hex=manifest["signature"],
            lock_sha256=manifest["lock_sha256"],
            tag=manifest["tag"],
            repo_url=manifest["repo_url"],
        )
    except (ValueError, InvalidSignature) as exc:
        console.print(f"[red]Signature verification failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    Path("uv.lock").write_text(lock_content, encoding="utf-8")

    try:
        run_uv_sync(frozen=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        console.print(f"[red]Failed to run uv sync --frozen:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    console.print("[green]Environment synced with `uv sync --frozen`.[/green]")


@app.command("list")
def list_command(prefix: str = typer.Option("", "--prefix", help="Only show tags with this prefix.")) -> None:
    """List snapshots from the configured server."""
    try:
        server = get_server_url()
        response = list_envs(server, prefix)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]List failed:[/red] {exc.response.status_code} {exc.response.text}")
        raise typer.Exit(code=1) from exc
    except httpx.HTTPError as exc:
        console.print(f"[red]Failed to reach server:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    table = Table(title="envr snapshots")
    table.add_column("Tag", style="cyan", no_wrap=True)
    table.add_column("Created")
    table.add_column("Python")
    table.add_column("Description")
    table.add_column("Repo URL")

    for item in response.get("items", []):
        table.add_row(
            item.get("tag", ""),
            item.get("created_at", ""),
            item.get("python_version", ""),
            item.get("description", ""),
            item.get("repo_url", ""),
        )

    console.print(table)


if __name__ == "__main__":
    app()
