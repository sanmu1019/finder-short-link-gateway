from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import Settings, create_app


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []
        self.ready = True
        self.reloads = 0

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def status(self) -> dict[str, Any]:
        return {
            "browser_started": True,
            "ready": self.ready,
            "reason": "" if self.ready else "login_required",
        }

    async def reload(self) -> None:
        self.reloads += 1

    async def share_url(
        self,
        object_id: str,
        object_nonce_id: str,
        scene: int,
    ) -> str:
        self.calls.append(
            (object_id, object_nonce_id, scene)
        )
        return "https://weixin.qq.com/sph/TestCode123"


def settings() -> Settings:
    return Settings(
        api_key="test-key",
        page_url="https://channels.weixin.qq.com/platform/",
        profile_dir=Path("/tmp/test-profile"),
        headless=True,
        request_timeout=5,
        startup_timeout=5,
    )


def test_share_url_forwards_ids_without_echoing_nonce() -> None:
    gateway = FakeGateway()
    app = create_app(settings(), gateway)
    object_id = "12345678901234567890"
    nonce = "n" * 24

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/finder/share-url",
            params={
                "object_id": object_id,
                "object_nonce_id": nonce,
                "scene": 40,
            },
            headers={"X-API-Key": "test-key"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["sph_url"].startswith(
        "https://weixin.qq.com/sph/"
    )
    assert nonce not in response.text
    assert gateway.calls == [
        (
            object_id,
            nonce,
            40,
        )
    ]


def test_api_key_is_required() -> None:
    app = create_app(settings(), FakeGateway())

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/finder/share-url",
            params={
                "object_id": "1",
                "object_nonce_id": "nonce",
            },
        )

    assert response.status_code == 401


def test_ready_reports_login_requirement() -> None:
    gateway = FakeGateway()
    gateway.ready = False
    app = create_app(settings(), gateway)

    with TestClient(app) as client:
        response = client.get(
            "/ready",
            headers={"X-API-Key": "test-key"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "login_required"
