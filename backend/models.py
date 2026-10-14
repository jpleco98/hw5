"""Data types shared by the Campus Customs agent team.

- AgentName / ROLE_TITLES: the five roles.
- TeamDeps: what every agent run carries (which ticket, who called whom, budgets).
- AgentReport: structured output of a specialist (Inventory, Accounting, Facilities,
  Customer Service) handed back to whoever delegated to it.
- TicketOutcome: Boss's final call on a ticket.
- AuditEntry: one line of output/audit_trail.json (one agent-loop step).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

ROLE_TITLES: dict[str, str] = {
    "boss": "Boss",
    "inventory": "Inventory",
    "accounting": "Accounting",
    "facilities": "Facilities",
    "customer_service": "Customer Service",
}


# ---------------------------------------------------------------------------
# Run context
# ---------------------------------------------------------------------------


@dataclass
class TicketBudget:
    """Counters shared by every agent run on one ticket (the whole delegation tree)."""

    max_delegations: int
    delegations_used: int = 0


@dataclass
class TeamDeps:
    """Passed to every agent run. A delegated run gets a child copy (depth + 1, longer chain)."""

    agent: AgentName
    ticket_id: int | None
    session_id: str  # one board run (all tickets in one go)
    run_id: str  # this agent run
    parent_run_id: str | None
    chain: list[AgentName]  # e.g. ["boss", "accounting"]: who delegated to whom
    depth: int
    max_depth: int
    budget: TicketBudget
    reports: list[dict[str, Any]] = field(default_factory=list)  # delegation results (for the outcome)


# ---------------------------------------------------------------------------
# Agent outputs
# ---------------------------------------------------------------------------


class Fact(BaseModel):
    """One fact the agent relied on, with the MCP tool it came from."""

    label: str = Field(description="What the fact is, e.g. 'CC-TEE-WHITE S on hand'")
    value: str = Field(description="The value exactly as the tool returned it, e.g. '0'")
    source_tool: str = Field(description="MCP tool that returned it, e.g. 'check_stock'")


class AgentReport(BaseModel):
    """What a specialist hands back to the agent that delegated work to it."""

    agent: AgentName
    ticket_id: int | None
    summary: str = Field(description="Two to four sentences: what you found and what you did")
    facts: list[Fact] = Field(default_factory=list, description="Key numbers and dates, each from a tool")
    actions_taken: list[str] = Field(
        default_factory=list, description="Board writes you made (payment requests, drafts), with ids"
    )
    payment_request_ids: list[int] = Field(default_factory=list)
    draft_ids: list[int] = Field(default_factory=list)
    recommendation: str = Field(description="What you recommend the Boss decide or do next")
    needs_human_approval: bool = Field(
        description="True if anything you prepared (e.g. a payment) waits for a human"
    )
    blockers: list[str] = Field(default_factory=list, description="What stops the ticket from closing")


TicketStatus = Literal["in_progress", "waiting_on_approval", "waiting_on_vendor", "resolved"]


class TicketOutcome(BaseModel):
    """Boss's final call on one ticket."""

    ticket_id: int
    decision: str = Field(description="The final call, in plain words (what the shop will do)")
    rationale: str = Field(description="Why, citing the facts and shop rules it rests on")
    status: TicketStatus = Field(description="Status you set on the board with update_ticket")
    delegated_to: list[AgentName] = Field(default_factory=list)
    payment_request_ids: list[int] = Field(
        default_factory=list, description="Payments waiting for HUMAN approval"
    )
    draft_ids: list[int] = Field(default_factory=list, description="Drafts saved on the board")
    human_next_steps: list[str] = Field(
        default_factory=list, description="What a person must do next (approve request #N, review draft #M)"
    )
    risks: list[str] = Field(default_factory=list, description="Cash conflicts, delays, open questions")


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

AuditEvent = Literal[
    "run_start",  # agent received its task
    "model_response",  # the model answered: text and/or tool calls
    "tool_results",  # tool results sent back to the model
    "delegation_refused",  # a delegate() call blocked by a guardrail
    "run_retry",  # output budget ran out before an answer; resumed once to get the final output
    "run_end",  # final structured output
    "run_error",  # the run failed (limit hit, model error, ...)
]


class ToolCallRecord(BaseModel):
    tool: str
    call_id: str | None = None
    args: dict[str, Any] | str | None = None


class ToolResultRecord(BaseModel):
    tool: str
    call_id: str | None = None
    ok: bool = True
    result: str = Field(description="Tool output, truncated for the log")


class UsageRecord(BaseModel):
    requests: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class AuditEntry(BaseModel):
    """One agent-loop step. Appended to output/audit_trail.json; the file is never wiped."""

    ts: str = Field(description="Wall-clock UTC time of the step")
    session_id: str
    ticket_id: int | None
    run_id: str
    parent_run_id: str | None
    agent: AgentName
    chain: list[str]
    depth: int
    step: int = Field(description="Step number inside this agent run")
    event: AuditEvent
    model: str
    prompt: str | None = None
    text: str | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    tool_results: list[ToolResultRecord] = Field(default_factory=list)
    step_usage: UsageRecord | None = None
    cumulative_usage: UsageRecord | None = Field(None, description="Whole ticket so far (shared budget)")
    output: dict[str, Any] | None = None
    error: str | None = None
