"""End-to-end API tests for the onboarding endpoints."""
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def http_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestStartSession:
    async def test_returns_201_with_session(self, http_client: AsyncClient) -> None:
        response = await http_client.post(
            "/api/v1/onboarding/sessions",
            json={"user_id": str(uuid4()), "locale": "pt-BR"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["state"] == "new"
        assert body["revision"] >= 1  # greeting bumps revision
        assert len(body["messages"]) == 1
        assert body["messages"][0]["role"] == "assistant"

    async def test_validates_user_id_format(self, http_client: AsyncClient) -> None:
        response = await http_client.post(
            "/api/v1/onboarding/sessions", json={"user_id": "not-a-uuid"}
        )
        assert response.status_code == 422


class TestSendMessage:
    async def test_send_and_receive(self, http_client: AsyncClient) -> None:
        start_resp = await http_client.post(
            "/api/v1/onboarding/sessions",
            json={"user_id": str(uuid4()), "locale": "pt-BR"},
        )
        session_id = start_resp.json()["id"]

        msg_resp = await http_client.post(
            f"/api/v1/onboarding/sessions/{session_id}/messages",
            json={"content": "olá, sou o Marcos"},
        )
        assert msg_resp.status_code == 200
        body = msg_resp.json()
        assert body["session"]["state"] == "in_progress"
        assert body["user_message"]["content"] == "olá, sou o Marcos"
        assert "olá, sou o Marcos" in body["assistant_message"]["content"]
        assert body["session"]["message_count"] == 3

    async def test_send_to_unknown_session_returns_404(
        self, http_client: AsyncClient
    ) -> None:
        response = await http_client.post(
            f"/api/v1/onboarding/sessions/{uuid4()}/messages",
            json={"content": "hi"},
        )
        assert response.status_code == 404
        assert response.json()["code"] == "SESSION_NOT_FOUND"


class TestGetSession:
    async def test_resume_includes_full_history(
        self, http_client: AsyncClient
    ) -> None:
        start_resp = await http_client.post(
            "/api/v1/onboarding/sessions",
            json={"user_id": str(uuid4()), "locale": "pt-BR"},
        )
        session_id = start_resp.json()["id"]
        await http_client.post(
            f"/api/v1/onboarding/sessions/{session_id}/messages",
            json={"content": "primeira"},
        )
        await http_client.post(
            f"/api/v1/onboarding/sessions/{session_id}/messages",
            json={"content": "segunda"},
        )

        get_resp = await http_client.get(f"/api/v1/onboarding/sessions/{session_id}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        # greeting + 2 user + 2 assistant
        assert body["message_count"] == 5
        assert len(body["messages"]) == 5
        # Sequences are monotonic.
        seqs = [m["sequence"] for m in body["messages"]]
        assert seqs == sorted(seqs)