"""FastAPI application for signed uv.lock snapshot sharing."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from envr_server.database import Database, SnapshotExistsError, SnapshotRecord
from envr_server.signing import SigningService
from envr_server.storage import SnapshotStorage

TAG_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class Settings(BaseModel):
    """Configuration for the envr server."""

    port: int = Field(default=8000)
    db_path: Path = Field(default=Path("/srv/envr/metadata.db"))
    key_path: Path = Field(default=Path("/etc/envr/server.key"))
    snapshots_dir: Path = Field(default=Path("/srv/envr/snapshots"))


class PushRequest(BaseModel):
    """Request payload for uploading a snapshot."""

    lock_content: str
    python_version: str
    description: str = ""
    repo_url: str = ""


class SnapshotResponse(BaseModel):
    """Snapshot response payload shared across endpoints."""

    tag: str
    created_at: str
    lock_sha256: str
    signature: str
    public_key: str
    python_version: str
    description: str
    repo_url: str


class PullResponse(SnapshotResponse):
    """Response payload for snapshot retrieval."""

    lock_content: str


class SnapshotListResponse(BaseModel):
    """Response payload for listing snapshots."""

    items: list[SnapshotResponse]


@dataclass(slots=True)
class Services:
    """Runtime services used by API endpoints."""

    database: Database
    storage: SnapshotStorage
    signing: SigningService


def get_settings() -> Settings:
    """Read settings from environment variables."""
    return Settings(
        port=int(os.getenv("ENVR_SERVER_PORT", "8000")),
        db_path=Path(os.getenv("ENVR_DB_PATH", "/srv/envr/metadata.db")),
        key_path=Path(os.getenv("ENVR_KEY_PATH", "/etc/envr/server.key")),
        snapshots_dir=Path(os.getenv("ENVR_SNAPSHOTS_DIR", "/srv/envr/snapshots")),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI app."""
    settings = settings or get_settings()
    api = FastAPI(title="envr server", version="0.1.0")

    def get_services() -> Services:
        existing = getattr(api.state, "services", None)
        if existing is not None:
            return existing

        database = Database(settings.db_path)
        database.initialize()
        services = Services(
            database=database,
            storage=SnapshotStorage(settings.snapshots_dir),
            signing=SigningService(settings.key_path),
        )
        api.state.services = services
        return services

    @api.get("/health")
    def health() -> dict[str, str]:
        """Healthcheck endpoint."""
        return {"status": "ok"}

    @api.post("/envs/{tag}", response_model=SnapshotResponse)
    def push_snapshot(tag: str, payload: PushRequest) -> SnapshotResponse:
        """Store and sign a new immutable snapshot tag."""
        _validate_tag(tag)
        services = get_services()

        if services.database.get_snapshot(tag) or services.storage.exists(tag):
            raise HTTPException(status_code=409, detail="Tag already exists")

        lock_sha256 = hashlib.sha256(payload.lock_content.encode("utf-8")).hexdigest()
        signature = services.signing.sign(lock_sha256, tag, payload.repo_url)
        created_at = datetime.now(timezone.utc).isoformat()

        services.storage.write(tag, payload.lock_content)
        record = SnapshotRecord(
            tag=tag,
            created_at=created_at,
            lock_sha256=lock_sha256,
            signature=signature,
            public_key=services.signing.public_key_hex,
            python_version=payload.python_version,
            description=payload.description,
            repo_url=payload.repo_url,
        )

        try:
            services.database.insert_snapshot(record)
        except SnapshotExistsError as exc:
            services.storage.delete(tag)
            raise HTTPException(status_code=409, detail="Tag already exists") from exc

        return SnapshotResponse(**asdict(record))

    @api.get("/envs/{tag}", response_model=PullResponse)
    def pull_snapshot(tag: str) -> PullResponse:
        """Retrieve snapshot metadata and lock content by tag."""
        _validate_tag(tag)
        services = get_services()
        metadata = services.database.get_snapshot(tag)
        if metadata is None:
            raise HTTPException(status_code=404, detail="Tag not found")

        try:
            lock_content = services.storage.read(tag)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail="Snapshot file missing") from exc

        return PullResponse(lock_content=lock_content, **metadata)

    @api.get("/envs", response_model=SnapshotListResponse)
    def list_snapshots(prefix: Annotated[str | None, Query()] = None) -> SnapshotListResponse:
        """List all snapshot metadata, optionally filtered by tag prefix."""
        services = get_services()
        items = [SnapshotResponse(**item) for item in services.database.list_snapshots(prefix)]
        return SnapshotListResponse(items=items)

    return api


def _validate_tag(tag: str) -> None:
    """Validate snapshot tag format."""
    if not TAG_PATTERN.fullmatch(tag):
        raise HTTPException(status_code=400, detail="Invalid tag")


app = create_app()


def run() -> None:
    """Run the FastAPI server using uvicorn."""
    settings = get_settings()
    uvicorn.run("envr_server.main:app", host="0.0.0.0", port=settings.port)
