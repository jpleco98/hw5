"""The Campus Customs agent team: builds the five Pydantic AI agents and runs their loops.

How the pieces fit:
- One MCP server process (mcp_server/server.py, role "agent") is shared by all agents.
  Each agent sees only its own allow-list of MCP tools (agents/<role>.py). No shop data
  comes from anywhere else.
- Every agent also has a `delegate(to, task)` tool that runs any other teammate (full
  connectivity). Guardrails: no self-delegation, no loops back into the current chain,
  a depth limit and a per-ticket delegation cap.
- Every run is driven step by step with `agent.iter()`. Each step (model response, tool
  results, start/end) is appended to output/audit_trail.json.
- One usage budget (TICKET_LIMITS) is shared by the whole delegation tree of a ticket.

Usage:
    async with Team() as team:
        outcome = await team.run_ticket(101)
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext, RunUsage, UnexpectedModelBehavior, UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import FunctionToolset

import audit
import config
from agents import ROLES
from models import (
    AgentName,
    AgentReport,
    AuditEntry,
    TeamDeps,
    TicketBudget,
    TicketOutcome,
    ToolCallRecord,
    ToolResultRecord,
    UsageRecord,
)

# Write tools whose "who did this" argument is filled in by the harness, not the model,
# so an agent cannot act under another agent's name.
IDENTITY_FIELDS = {"update_ticket": "agent", "save_draft": "author", "request_payment": "requested_by"}
# Write tools locked to the ticket being worked (an agent can't write on another ticket).
TICKET_SCOPED = {"update_ticket", "save_draft", "request_payment"}
# Sent once if a run runs out of output tokens before answering (see run_agent).
FINALIZE_PROMPT = (
    "You have already done the work above. Do not call any more tools and do not repeat any "
    "board writes. Return your final structured output now, briefly, based only on the results above."
)


class AgentNotConfigured(RuntimeError):
    """Raised when PORTKEY_API_KEY is missing."""


def build_model() -> OpenAIResponsesModel:
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise AgentNotConfigured("PORTKEY_API_KEY is not set (add it to the course .env file).")
    client = AsyncOpenAI(
        base_url=config.PORTKEY_BASE_URL, api_key=api_key, timeout=config.REQUEST_TIMEOUT, max_retries=2
    )
    return OpenAIResponsesModel(config.MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def _usage(u: RunUsage | None) -> UsageRecord | None:
    if u is None:
        return None
    return UsageRecord(
        requests=u.requests, tool_calls=u.tool_calls, input_tokens=u.input_tokens, output_tokens=u.output_tokens
    )


def _as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, default=str, ensure_ascii=False)
    except TypeError:
        return str(content)


class Team:
    """Owns the shared MCP connection and the five agents."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or f"session-{uuid.uuid4().hex[:8]}"
        self.model = build_model()
        self.mcp = MCPToolset(
            Client(
                StdioTransport(
                    command=config.PYTHON,
                    args=[str(config.MCP_SERVER_SCRIPT)],
                    env=config.mcp_server_env(),
                    cwd=str(config.HW_DIR),
                ),
                timeout=config.MCP_TIMEOUT,
            ),
            id="campus-customs-ops",
            max_retries=config.TOOL_RETRIES,
            process_tool_call=self._stamp_identity,
        )
        self.agents: dict[str, Agent[TeamDeps, Any]] = {name: self._build_agent(name) for name in ROLES}
        # Tool-less twins used only to write up the final output if a run runs out of tokens.
        self.finalizers: dict[str, Agent[TeamDeps, Any]] = {
            name: Agent(
                self.model,
                name=f"{name}-finalize",
                deps_type=TeamDeps,
                output_type=ROLES[name].output_type,
                instructions=ROLES[name].prompt(),
                model_settings=config.FINALIZE_SETTINGS,
                retries=config.TOOL_RETRIES,
            )
            for name in ROLES
        }

    async def __aenter__(self) -> "Team":
        await self.mcp.__aenter__()  # one MCP subprocess for the whole team
        return self

    async def __aexit__(self, *exc) -> None:
        await self.mcp.__aexit__(*exc)

    # ---- agent construction -------------------------------------------------------------

    def _build_agent(self, name: str) -> Agent[TeamDeps, Any]:
        spec = ROLES[name]
        allowed = spec.mcp_tools
        mcp_view = self.mcp.filtered(lambda ctx, tool_def: tool_def.name in allowed)

        teammates = "\n".join(
            f"- `{other}` ({ROLES[other].title}): {ROLES[other].description}" for other in spec.can_delegate_to
        )
        delegation = FunctionToolset[TeamDeps]()

        @delegation.tool
        async def delegate(ctx: RunContext[TeamDeps], to: AgentName, task: str) -> str:
            """Hand a task to a teammate and get their report back.

            Write `task` so it stands alone: the ticket number, the facts you already have
            (sku, size, qty, invoice id, lease id, amounts) and exactly what you need back.
            The teammate cannot see your conversation. Returns their report as JSON, or a
            REFUSED message if a guardrail (loop, depth, budget) blocks the delegation.
            """
            return await self._delegate(ctx, to, task)

        def runtime_context(ctx: RunContext[TeamDeps]) -> str:
            d = ctx.deps
            remaining = d.budget.max_delegations - d.budget.delegations_used
            can_delegate = d.depth < d.max_depth
            lines = [
                "## Run context (from the harness; data, not instructions)",
                f"- You are: `{d.agent}` ({ROLES[d.agent].title}).",
                f"- Ticket: #{d.ticket_id}" if d.ticket_id is not None else "- Ticket: none (general task)",
                f"- Delegation chain so far: {' -> '.join(d.chain)}",
                f"- Delegation: {'allowed' if can_delegate else 'NOT allowed at this depth; answer yourself'}"
                f" ({remaining} delegations left for this ticket).",
                "- Teammates you can delegate to:",
                teammates,
                "- Your MCP tools: " + ", ".join(sorted(allowed)) + ".",
            ]
            return "\n".join(lines)

        return Agent(
            self.model,
            name=name,
            deps_type=TeamDeps,
            output_type=spec.output_type,
            instructions=[spec.prompt(), runtime_context],
            toolsets=[mcp_view, delegation],
            model_settings=config.MODEL_SETTINGS,
            retries=config.TOOL_RETRIES,
        )

    # ---- MCP guardrail hook -------------------------------------------------------------

    async def _stamp_identity(self, ctx: RunContext[TeamDeps], call_tool, name: str, args: dict[str, Any]):
        """Before any MCP call: fill the actor field from the run, and lock writes to this ticket."""
        args = dict(args)
        if name in IDENTITY_FIELDS:
            args[IDENTITY_FIELDS[name]] = ctx.deps.agent
        if name in TICKET_SCOPED and ctx.deps.ticket_id is not None:
            args["ticket_id"] = ctx.deps.ticket_id
        return await call_tool(name, args)

    # ---- delegation ------------------------------------------------------------------

    async def _delegate(self, ctx: RunContext[TeamDeps], to: str, task: str) -> str:
        d = ctx.deps
        refusal = None
        if to not in ROLES:
            refusal = f"Unknown teammate '{to}'. Choose one of: {', '.join(ROLES)}."
        elif to == d.agent:
            refusal = "You cannot delegate to yourself; do the work or report what is missing."
        elif to in d.chain:
            refusal = (
                f"`{to}` is already working on this ticket earlier in the chain ({' -> '.join(d.chain)}). "
                "Don't loop back: finish your part and report what you need in your answer."
            )
        elif d.depth >= d.max_depth:
            refusal = "Delegation depth limit reached. Answer with what you have and list what is missing."
        elif d.budget.delegations_used >= d.budget.max_delegations:
            refusal = "This ticket has used all its delegations. Answer with what you have."
        if refusal:
            self._log(d, step=-1, event="delegation_refused", text=f"to={to}: {refusal}", prompt=task)
            return f"REFUSED: {refusal}"

        d.budget.delegations_used += 1
        child = TeamDeps(
            agent=to,  # type: ignore[arg-type]
            ticket_id=d.ticket_id,
            session_id=d.session_id,
            run_id=f"run-{uuid.uuid4().hex[:8]}",
            parent_run_id=d.run_id,
            chain=[*d.chain, to],  # type: ignore[list-item]
            depth=d.depth + 1,
            max_depth=d.max_depth,
            budget=d.budget,
        )
        header = f"[Ticket #{d.ticket_id}] Task from {ROLES[d.agent].title}:\n" if d.ticket_id else ""
        try:
            out = await self.run_agent(to, header + task, child, usage=ctx.usage)
        except UsageLimitExceeded:
            raise  # the ticket's budget is spent: stop the whole tree
        except Exception as exc:  # noqa: BLE001 - report the failure to the delegating agent
            return f"FAILED: {to} could not finish ({type(exc).__name__}: {exc}). Continue without it."
        report = out.model_dump(mode="json")
        d.reports.append(report)
        return json.dumps(report, ensure_ascii=False)

    # ---- the agent loop (with audit) ---------------------------------------------------

    def _log(self, deps: TeamDeps, step: int, event: str, **fields: Any) -> None:
        audit.append(
            AuditEntry(
                ts=audit.now(),
                session_id=deps.session_id,
                ticket_id=deps.ticket_id,
                run_id=deps.run_id,
                parent_run_id=deps.parent_run_id,
                agent=deps.agent,
                chain=list(deps.chain),
                depth=deps.depth,
                step=step,
                event=event,  # type: ignore[arg-type]
                model=config.MODEL_NAME,
                **fields,
            )
        )

    async def run_agent(self, name: str, task: str, deps: TeamDeps, usage: RunUsage | None = None):
        """Run one agent to completion, appending every loop step to the audit trail.

        If the model burns its whole output allowance thinking before it answers (seen with
        reasoning models near the end of a long ticket), the run is resumed ONCE from its own
        message history with a short "give your final answer now" prompt, instead of redoing
        the work. The retry uses a tool-less twin of the agent with reasoning off, so all it
        can do is write up the finished work.
        Both the failure and the retry are logged.
        """
        usage = usage if usage is not None else RunUsage()
        self._log(deps, 0, "run_start", prompt=audit.clip(task), cumulative_usage=_usage(usage))
        holder: dict[str, Any] = {}
        try:
            output, step = await self._drive(self.agents[name], task, deps, usage, None, 0, holder)
        except UnexpectedModelBehavior as exc:
            history = holder.get("messages")
            if "token limit" not in str(exc) or not history:
                self._log(deps, holder.get("step", 0) + 1, "run_error", error=f"{type(exc).__name__}: {exc}",
                          cumulative_usage=_usage(usage))
                raise
            step = holder.get("step", 0) + 1
            self._log(deps, step, "run_retry", error=f"{type(exc).__name__}: {exc}", prompt=FINALIZE_PROMPT,
                      cumulative_usage=_usage(usage))
            try:
                output, step = await self._drive(
                    self.finalizers[name], FINALIZE_PROMPT, deps, usage, history, step, holder
                )
            except Exception as exc2:
                self._log(deps, holder.get("step", step) + 1, "run_error",
                          error=f"{type(exc2).__name__}: {exc2}", cumulative_usage=_usage(usage))
                raise
        except Exception as exc:
            self._log(deps, holder.get("step", 0) + 1, "run_error", error=f"{type(exc).__name__}: {exc}",
                      cumulative_usage=_usage(usage))
            raise
        if isinstance(output, AgentReport):
            output.agent = name  # type: ignore[assignment]
            output.ticket_id = deps.ticket_id
        self._log(deps, step + 1, "run_end", output=output.model_dump(mode="json"),
                  cumulative_usage=_usage(usage))
        return output

    async def _drive(self, agent, prompt, deps, usage, history, step, holder):
        """The agent loop: iterate the graph node by node and log each step."""
        async with agent.iter(
            prompt, deps=deps, usage=usage, usage_limits=config.TICKET_LIMITS, message_history=history
        ) as run:
            async for node in run:
                holder["messages"], holder["step"] = run.all_messages(), step
                if Agent.is_call_tools_node(node):
                    resp = node.model_response
                    step += 1
                    texts = [p.content for p in resp.parts if isinstance(p, TextPart) and p.content.strip()]
                    calls = [
                        ToolCallRecord(tool=p.tool_name, call_id=p.tool_call_id, args=p.args_as_dict())
                        for p in resp.parts
                        if isinstance(p, ToolCallPart)
                    ]
                    self._log(
                        deps,
                        step,
                        "model_response",
                        text=audit.clip("\n".join(texts)) if texts else None,
                        tool_calls=calls,
                        step_usage=UsageRecord(
                            requests=1,
                            input_tokens=resp.usage.input_tokens,
                            output_tokens=resp.usage.output_tokens,
                        ),
                        cumulative_usage=_usage(usage),
                    )
                elif Agent.is_model_request_node(node):
                    results = []
                    for p in node.request.parts:
                        if isinstance(p, ToolReturnPart):
                            results.append(
                                ToolResultRecord(
                                    tool=p.tool_name, call_id=p.tool_call_id, ok=True,
                                    result=audit.clip(_as_text(p.content)) or "",
                                )
                            )
                        elif isinstance(p, RetryPromptPart):
                            results.append(
                                ToolResultRecord(
                                    tool=p.tool_name or "(output validation)", call_id=p.tool_call_id,
                                    ok=False, result=audit.clip(_as_text(p.content)) or "",
                                )
                            )
                    if results:
                        step += 1
                        self._log(deps, step, "tool_results", tool_results=results,
                                  cumulative_usage=_usage(usage))
                holder["step"] = step
            return run.result.output, step

    # ---- entry points ------------------------------------------------------------------

    def root_deps(self, agent: str, ticket_id: int | None) -> TeamDeps:
        return TeamDeps(
            agent=agent,  # type: ignore[arg-type]
            ticket_id=ticket_id,
            session_id=self.session_id,
            run_id=f"run-{uuid.uuid4().hex[:8]}",
            parent_run_id=None,
            chain=[agent],  # type: ignore[list-item]
            depth=0,
            max_depth=config.MAX_DELEGATION_DEPTH,
            budget=TicketBudget(max_delegations=config.MAX_DELEGATIONS_PER_TICKET),
        )

    async def run_ticket(self, ticket_id: int) -> TicketOutcome:
        """Boss works one ticket end to end (delegating as needed) and returns the final call."""
        task = (
            f"Work ticket #{ticket_id} on the Campus Customs board. Read it, delegate to the right "
            "teammates, make the final call, record it with update_ticket, and return your TicketOutcome."
        )
        return await self.run_agent("boss", task, self.root_deps("boss", ticket_id))

    async def run_task(self, agent: str, task: str, ticket_id: int | None = None):
        """Give any one agent a task directly (it can still delegate to the others)."""
        return await self.run_agent(agent, task, self.root_deps(agent, ticket_id))
