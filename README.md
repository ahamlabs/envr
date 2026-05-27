# envr

`envr` shares reproducible Python environments via signed `uv.lock` snapshots.

## Repo layout

- `envr_server/`: FastAPI server package (`envr-server`)
- `envr_cli/`: Typer CLI package (`envr`)

## Server quickstart

```bash
uv run uvicorn envr_server.main:app --reload
```

Server environment variables:

- `ENVR_SERVER_PORT` (default `8000`)
- `ENVR_DB_PATH` (default `/srv/envr/metadata.db`)
- `ENVR_KEY_PATH` (default `/etc/envr/server.key`)
- `ENVR_SNAPSHOTS_DIR` (default `/srv/envr/snapshots`)

A systemd template is available at `envr_server/envr-server.service`.

## CLI quickstart

```bash
uv tool install .
envr config set server http://localhost:8000
envr push v1 --desc "initial lock"
envr list
envr pull v1
envr sync
```

The CLI stores config in `~/.envr/config.toml` and project manifest data in `.envr`.
