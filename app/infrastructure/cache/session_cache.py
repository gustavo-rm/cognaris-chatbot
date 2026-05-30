"""Redis cache for hot session state.

Cache-aside semantics:
- get(): try Redis first, fall back to None (caller hits Postgres).
- set(): write the serialized session, refresh TTL.
- invalidate(): drop the entry.

We store sessions as JSON because the data is small (typical session: a few KB
including ~20 messages) and JSON gives us human-readable Redis debugging.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import redis.asyncio as redis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.domain.onboarding.entities import ConversationMessage, OnboardingSession
from app.domain.onboarding.enums import ClientPlatform, MessageRole, SessionState

logger = get_logger(__name__)


class SessionCache:
    KEY_TEMPLATE = "session:{id}"

    def __init__(self, *, client: redis.Redis) -> None:
        self._client = client
        self._ttl = get_settings().session_ttl_seconds

    def _key(self, session_id: UUID) -> str:
        return self.KEY_TEMPLATE.format(id=session_id)

    async def get(self, session_id: UUID) -> OnboardingSession | None:
        raw = await self._client.get(self._key(session_id))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            return _deserialize(data)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            # Corrupt cache entry — log and force a Postgres fetch.
            logger.warning(
                "session_cache.deserialize_failed",
                session_id=str(session_id),
                error=str(exc),
            )
            await self.invalidate(session_id)
            return None

    async def set(self, session: OnboardingSession) -> None:
        try:
            payload = json.dumps(_serialize(session))
            await self._client.set(self._key(session.id), payload, ex=self._ttl)
        except Exception as exc:
            # Cache failures must not break the request path.
            logger.warning(
                "session_cache.set_failed", session_id=str(session.id), error=str(exc)
            )

    async def invalidate(self, session_id: UUID) -> None:
        try:
            await self._client.delete(self._key(session_id))
        except Exception as exc:
            logger.warning(
                "session_cache.invalidate_failed",
                session_id=str(session_id),
                error=str(exc),
            )


# --------- Serialization (domain entity <-> JSON-compatible dict) ---------


def _serialize(session: OnboardingSession) -> dict[str, Any]:
    return {
        "id": str(session.id),
        "user_id": str(session.user_id),
        "state": session.state.value,
        "revision": session.revision,
        "locale": session.locale,
        "client_platform": session.client_platform.value,
        "current_step": session.current_step,
        "started_at": session.started_at.isoformat(),
        "last_active_at": session.last_active_at.isoformat(),
        "expires_at": session.expires_at.isoformat(),
        "confirmed_at": session.confirmed_at.isoformat() if session.confirmed_at else None,
        "submitted_at": session.submitted_at.isoformat() if session.submitted_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "messages": [
            {
                "id": str(m.id),
                "session_id": str(m.session_id),
                "role": m.role.value,
                "content": m.content,
                "sequence": m.sequence,
                "created_at": m.created_at.isoformat(),
                "rich_payload": m.rich_payload,
                "metadata": m.metadata,
            }
            for m in session.messages
        ],
    }


def _deserialize(data: dict[str, Any]) -> OnboardingSession:
    messages = [
        ConversationMessage(
            id=UUID(m["id"]),
            session_id=UUID(m["session_id"]),
            role=MessageRole(m["role"]),
            content=m["content"],
            sequence=m["sequence"],
            created_at=datetime.fromisoformat(m["created_at"]),
            rich_payload=m.get("rich_payload"),
            metadata=m.get("metadata"),
        )
        for m in data["messages"]
    ]
    return OnboardingSession(
        id=UUID(data["id"]),
        user_id=UUID(data["user_id"]),
        state=SessionState(data["state"]),
        revision=data["revision"],
        locale=data["locale"],
        client_platform=ClientPlatform(data["client_platform"]),
        current_step=data.get("current_step"),
        started_at=datetime.fromisoformat(data["started_at"]),
        last_active_at=datetime.fromisoformat(data["last_active_at"]),
        expires_at=datetime.fromisoformat(data["expires_at"]),
        confirmed_at=(
            datetime.fromisoformat(data["confirmed_at"])
            if data.get("confirmed_at")
            else None
        ),
        submitted_at=(
            datetime.fromisoformat(data["submitted_at"])
            if data.get("submitted_at")
            else None
        ),
        completed_at=(
            datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None
        ),
        messages=messages,
    )