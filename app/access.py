"""Token capabilities shared by REST and MCP; sessions retain membership access."""

from contextvars import ContextVar
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Grant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace: str = Field(min_length=1)
    actions: list[Literal["read", "create", "update", "delete", "relate"]]
    pages: list[str] | None = None


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grants: list[Grant]


policy: ContextVar[dict | None] = ContextVar("token_policy", default=None)
actor: ContextVar[str | None] = ContextVar("token_actor", default=None)


def allowed(workspace: str, action: str, slug: str | None = None) -> bool:
    current = policy.get()
    if current is None:
        return True
    return any(
        g["workspace"] == workspace
        and action in g["actions"]
        and (g.get("pages") is None or slug is not None and slug in g["pages"])
        for g in current["grants"]
    )


def require(workspace: str, action: str, slug: str | None = None) -> None:
    if not allowed(workspace, action, slug):
        raise PermissionError("Token does not permit this operation")
