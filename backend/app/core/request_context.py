from __future__ import annotations

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
actor_user_id_var: ContextVar[str | None] = ContextVar("actor_user_id", default=None)


def request_id() -> str | None:
    return request_id_var.get()


def actor_user_id() -> str | None:
    return actor_user_id_var.get()
