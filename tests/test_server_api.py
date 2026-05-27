"""Focused tests for envr server API behavior."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from envr_server.main import Settings, create_app


def _make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        db_path=tmp_path / "metadata.db",
        key_path=tmp_path / "server.key",
        snapshots_dir=tmp_path / "snapshots",
    )
    return TestClient(create_app(settings))


def test_push_get_and_list_snapshot(tmp_path: Path) -> None:
    client = _make_client(tmp_path)

    push_payload = {
        "lock_content": "[[package]]\nname = \"httpx\"\nversion = \"0.27.0\"\n",
        "python_version": "3.12.2",
        "description": "test snapshot",
        "repo_url": "https://example.com/repo.git",
    }
    push_response = client.post("/envs/v1", json=push_payload)
    assert push_response.status_code == 200

    get_response = client.get("/envs/v1")
    assert get_response.status_code == 200
    pulled = get_response.json()
    assert pulled["lock_content"] == push_payload["lock_content"]
    assert pulled["lock_sha256"] == push_response.json()["lock_sha256"]

    list_response = client.get("/envs", params={"prefix": "v"})
    assert list_response.status_code == 200
    items = list_response.json()["items"]
    assert len(items) == 1
    assert items[0]["tag"] == "v1"


def test_tag_is_immutable(tmp_path: Path) -> None:
    client = _make_client(tmp_path)
    payload = {
        "lock_content": "content",
        "python_version": "3.12.2",
        "description": "first",
        "repo_url": "",
    }
    first = client.post("/envs/release-1", json=payload)
    assert first.status_code == 200

    second = client.post("/envs/release-1", json=payload)
    assert second.status_code == 409
