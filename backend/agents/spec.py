"""RoleSpec: everything that defines one agent on the team (no model or MCP wiring here)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@dataclass(frozen=True)
class RoleSpec:
    name: str  # matches models.AgentName
    title: str
    prompt_file: str  # file in backend/prompts/
    output_type: type[BaseModel]
    mcp_tools: frozenset[str]  # least privilege: the MCP tools this role may call
    can_delegate_to: tuple[str, ...]  # full connectivity: every other role
    description: str  # one line, shown to teammates in the delegate tool

    def prompt(self) -> str:
        return (PROMPTS_DIR / self.prompt_file).read_text(encoding="utf-8")
