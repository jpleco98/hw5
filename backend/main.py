r"""Campus Customs operations API: the backend the React dashboard calls.

Run from HW 5/backend:
    ..\\.venv\\Scripts\\activate
    uvicorn main:app --reload --port 8000        ->  http://localhost:8000  (docs at /docs)

Where data comes from:
- Shop facts (tickets, cash, payment requests) are read through the MCP server, the same
  tool layer the agents use, so there is no second shop-data layer.
- The backend keeps two MCP connections to mcp_server/server.py:
    * "agent" role, inside Team: what the five agents use. No tool there can move money.
    * "operator" role, below: used only by the human routes (approve / reject). This is the
      only path that can change cash.
- Agent events are read from output/audit_trail.json (append-only, written by team.py).
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastmcp import Client  # noqa: E402
from fastmcp.client.transports import StdioTransport  # noqa: E402
from fastmcp.exceptions import ToolError  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import audit  # noqa: E402
import config  # noqa: E402
import reset_db  # noqa: E402
from team import AgentNotConfigured, Team  # noqa: E402

# ---------------------------------------------------------------------------
# MCP connections and run state
# ---------------------------------------------------------------------------


def operator_client() -> Client:
    """MCP connection for HUMAN actions: same server, operator role (adds approve/reject)."""
    env = config.mcp_server_env()
    env["CAMPUS_CUSTOMS_MCP_ROLE"] = "operator"
    return Client(
        StdioTransport(command=config.PYTHON, args=[str(config.MCP_SERVER_SCRIPT)], env=env, cwd=str(config.HW_DIR)),
        timeout=config.MCP_TIMEOUT,
    )


class State:
    ops: Client | None = None
    team: Team | None = None
    team_error: str | None = None
    run_lock = asyncio.Lock()  # one agent run at a time (they share cash and the board)
    jobs: dict[str, dict[str, Any]] = {}


state = State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.ops = operator_client()
    await state.ops.__aenter__()
    try:
        state.team = Team(session_id=f"api-{uuid.uuid4().hex[:8]}")
        await state.team.__aenter__()
    except AgentNotConfigured as exc:  # the board still works; only /run is unavailable
        state.team, state.team_error = None, str(exc)
    try:
        yield
    finally:
        # Close both MCP subprocesses, but never let a stuck one block a --reload restart.
        for closer in ([state.team.__aexit__] if state.team is not None else []) + [state.ops.__aexit__]:
            try:
                await asyncio.wait_for(closer(None, None, None), timeout=5)
            except Exception:  # noqa: BLE001
                pass


app = FastAPI(title="Campus Customs Operations API", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp_call(tool: str, **args: Any) -> Any:
    """Call an MCP tool as the operator. Unknown ids -> 404; a rule refusal -> 409 with its message."""
    try:
        result = await state.ops.call_tool(tool, args)
    except ToolError as exc:
        code = 404 if str(exc).startswith("Unknown") else 409  # 409 = refused by a shop rule
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    data = result.structured_content
    if isinstance(data, dict) and set(data) == {"result"}:  # list returns are wrapped by MCP
        return data["result"]
    return data


# ---------------------------------------------------------------------------
# Request / response bodies
# ---------------------------------------------------------------------------


class ApproveBody(BaseModel):
    approved_by: str = Field(min_length=1, description="Name of the human who clicked Approve")
    account: str = "checking"


class RejectBody(BaseModel):
    rejected_by: str = Field(min_length=1)
    reason: str = ""


class TicketRow(BaseModel):
    ticket_id: int
    type: str
    requester: str
    subject: str
    notes: str | None
    sku: str | None
    size: str | None
    qty: int | None
    status: str = Field(description="Board status: open, in_progress, waiting_on_approval, waiting_on_vendor, resolved")
    state: Literal["open", "running", "resolved"] = Field(
        description="open = team hasn't worked it; running = agents on it now; "
        "resolved = the team finished its run and Boss recorded the final call (or status is resolved)"
    )
    running: bool = Field(description="An agent run is working on this ticket right now")
    pending_approvals: int = Field(description="Payment requests on this ticket waiting for a human")
    decision: str | None = Field(description="Boss's latest note on the board")
    draft_count: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "model": config.MODEL_NAME,
        "agents_ready": state.team is not None,
        "agents_error": state.team_error,
        "database": config.WORKING_DB.name,
    }


@app.get("/api/tickets", response_model=list[TicketRow])
async def list_tickets() -> list[TicketRow]:
    """Every ticket with its board status and whether it is open, running or resolved."""
    running = {j["ticket_id"] for j in state.jobs.values() if j["status"] in ("queued", "running")}
    rows = []
    for t in await mcp_call("list_tickets"):
        d = await mcp_call("get_ticket", ticket_id=t["ticket_id"])
        boss_notes = [u["note"] for u in d["updates"] if u["agent"] == "boss"]
        is_running = d["ticket_id"] in running
        state_ = "running" if is_running else (
            "resolved" if d["status"] == "resolved" or boss_notes else "open"
        )
        rows.append(
            TicketRow(
                ticket_id=d["ticket_id"], type=d["type"], requester=d["requester"], subject=d["subject"],
                notes=d["notes"], sku=d["sku"], size=d["size"], qty=d["qty"], status=d["status"],
                state=state_, running=is_running,
                pending_approvals=sum(r["status"] == "pending_approval" for r in d["payment_requests"]),
                decision=boss_notes[-1] if boss_notes else None,
                draft_count=len(d["drafts"]),
            )
        )
    return rows


@app.get("/api/tickets/{ticket_id}")
async def ticket_detail(ticket_id: int) -> dict[str, Any]:
    """One ticket in full: linked invoice/lease, status history, drafts and payment requests."""
    return await mcp_call("get_ticket", ticket_id=ticket_id)


async def _run_job(job: dict[str, Any]) -> None:
    async with state.run_lock:
        job["status"], job["started_at"] = "running", audit.now()
        try:
            outcome = await state.team.run_ticket(job["ticket_id"])
            job["status"], job["outcome"] = "done", outcome.model_dump(mode="json")
        except Exception as exc:  # noqa: BLE001 - surfaced to the dashboard
            job["status"], job["error"] = "failed", f"{type(exc).__name__}: {exc}"
        finally:
            job["finished_at"] = audit.now()


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int, wait: bool = False) -> dict[str, Any]:
    """Run the agent team (Boss first) on one ticket.

    Returns at once with a job id (poll /api/runs/{job_id} and /api/events), or, with
    ?wait=true, blocks until the Boss returns its TicketOutcome.
    """
    if state.team is None:
        raise HTTPException(503, f"Agents not available: {state.team_error}")
    await mcp_call("get_ticket", ticket_id=ticket_id)  # 409 if the ticket doesn't exist
    if any(j["status"] in ("queued", "running") for j in state.jobs.values()):
        raise HTTPException(409, "Another agent run is in progress; wait for it to finish.")
    job = {
        "job_id": f"job-{uuid.uuid4().hex[:8]}",
        "ticket_id": ticket_id,
        "status": "queued",
        "session_id": state.team.session_id,
        "queued_at": audit.now(),
        "audit_index_start": len(_read_audit()),
    }
    state.jobs[job["job_id"]] = job
    task = asyncio.create_task(_run_job(job))
    if wait:
        await task
    return job


@app.get("/api/runs")
async def list_runs() -> list[dict[str, Any]]:
    """Agent runs started through this server, newest first."""
    return sorted(state.jobs.values(), key=lambda j: j["queued_at"], reverse=True)


@app.get("/api/runs/{job_id}")
async def get_run(job_id: str) -> dict[str, Any]:
    if job_id not in state.jobs:
        raise HTTPException(404, f"Unknown job {job_id}")
    return state.jobs[job_id]


def _read_audit() -> list[dict[str, Any]]:
    with audit._lock:  # same lock the writer uses, so we never read a half-replaced file
        if not audit.AUDIT_PATH.exists() or not audit.AUDIT_PATH.stat().st_size:
            return []
        return json.loads(audit.AUDIT_PATH.read_text(encoding="utf-8"))


def _said(e: dict[str, Any]) -> str | None:
    """What the agent said at this step, in one readable string."""
    if e["event"] == "run_start":
        return e.get("prompt")
    if e["event"] == "run_end":
        out = e.get("output") or {}
        return out.get("decision") or out.get("summary")
    if e["event"] in ("run_error", "delegation_refused"):
        return e.get("error") or e.get("text")
    return e.get("text")


@app.get("/api/events")
async def events(
    since: int = Query(-1, description="Return events with index > since (use next_since to poll)"),
    ticket_id: int | None = None,
    agent: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """Recent agent events from the audit trail: who acted, what they said, which tools they used.

    Poll with ?since=<next_since> to get only what is new since the last refresh.
    """
    entries = _read_audit()
    rows = []
    for i, e in enumerate(entries):
        if i <= since or (ticket_id is not None and e.get("ticket_id") != ticket_id):
            continue
        if agent and e.get("agent") != agent:
            continue
        calls = e.get("tool_calls") or []
        rows.append(
            {
                "index": i,
                "ts": e["ts"],
                "ticket_id": e.get("ticket_id"),
                "agent": e["agent"],
                "event": e["event"],
                "depth": e.get("depth", 0),
                "chain": e.get("chain", []),
                "run_id": e["run_id"],
                "parent_run_id": e.get("parent_run_id"),
                "said": _said(e),
                "tools_used": [c["tool"] for c in calls],
                "tool_calls": calls,
                "delegations": [
                    {"to": (c.get("args") or {}).get("to"), "task": (c.get("args") or {}).get("task")}
                    for c in calls
                    if c["tool"] == "delegate" and isinstance(c.get("args"), dict)
                ],
                "tool_results": [
                    {"tool": r["tool"], "ok": r.get("ok", True), "result": audit.clip(r.get("result"), 400)}
                    for r in e.get("tool_results") or []
                ],
                "cumulative_usage": e.get("cumulative_usage"),
                "output": e.get("output"),  # final report / decision on run_end
                "error": e.get("error"),
            }
        )
    rows = rows[-limit:]
    return {"events": rows, "next_since": len(entries) - 1, "total": len(entries)}


async def _payee(r: dict[str, Any]) -> str:
    """Who the money would go to, for the check the human signs."""
    try:
        if r["kind"] == "invoice":
            return (await mcp_call("get_invoice", invoice_id=r["ref_id"]))["vendor_name"]
        if r["kind"] == "rent":
            return (await mcp_call("get_rent_status", lease_id=r["ref_id"]))["landlord"]
        return (await mcp_call("get_vendor_status", vendor_id=r["vendor_id"]))["vendors"][0]["name"]
    except HTTPException:
        return "(unknown payee)"


@app.get("/api/payment-requests")
async def payment_requests(status: str | None = "pending_approval") -> list[dict[str, Any]]:
    """Payment and purchase-order requests the agents prepared (default: the ones awaiting a human)."""
    rows = await mcp_call("list_payment_requests", status=status)
    for r in rows:
        r["payee"] = await _payee(r)
    return rows


@app.post("/api/payment-requests/{request_id}/approve")
async def approve_payment(request_id: int, body: ApproveBody) -> dict[str, Any]:
    """HUMAN action: approve and pay a request. This is the only route that changes cash.

    The MCP tool refuses (HTTP 409) if cash is short, the invoice isn't open, or a
    purchase-order vendor is still blocked; nothing changes in that case. When the last
    pending request on a ticket is paid, the ticket moves on: rent -> resolved, invoice or
    purchase order -> waiting_on_vendor (the product still has to arrive).
    """
    if state.run_lock.locked():
        raise HTTPException(409, "An agent run is in progress; approve when it finishes.")
    result = await mcp_call(
        "approve_and_pay", request_id=request_id, approved_by=body.approved_by, account=body.account
    )
    req = result["request"]
    ticket = await mcp_call("get_ticket", ticket_id=req["ticket_id"])
    still_pending = [r for r in ticket["payment_requests"] if r["status"] == "pending_approval"]
    if not still_pending and ticket["status"] == "waiting_on_approval":
        new_status = "resolved" if req["kind"] == "rent" else "waiting_on_vendor"
        await mcp_call(
            "update_ticket", ticket_id=req["ticket_id"], status=new_status, agent=f"human:{body.approved_by}",
            note=f"All payments on this ticket approved by {body.approved_by}; moved to {new_status}.",
        )
        result["ticket_status"] = new_status
    return result


@app.post("/api/payment-requests/{request_id}/reject")
async def reject_payment(request_id: int, body: RejectBody) -> dict[str, Any]:
    """HUMAN action: reject a request. No money moves."""
    return await mcp_call(
        "reject_payment_request", request_id=request_id, rejected_by=body.rejected_by, reason=body.reason
    )


@app.get("/api/cash")
async def cash() -> dict[str, Any]:
    """Current checking balance from cash_accounts, plus what is pending approval."""
    pos = await mcp_call("get_cash_position")
    checking = next((a for a in pos["accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(500, "No 'checking' row in cash_accounts.")
    return {
        "account": "checking",
        "balance": checking["balance"],
        "as_of": pos["as_of"],
        "pending_total": pos["pending_total"],
        "cash_after_pending": pos["cash_after_pending"],
        "payments_made": pos["payments_made"],
    }


@app.post("/api/reset")
async def reset() -> dict[str, Any]:
    """Reset data/campus_customs_new.db to the original values for a fresh run.

    The original database and the audit trail are not touched.
    """
    if state.run_lock.locked():
        raise HTTPException(409, "An agent run is in progress; reset when it finishes.")
    reset_db.reset()
    state.jobs.clear()
    return {
        "reset": True,
        "database": config.WORKING_DB.name,
        "from": config.ORIGINAL_DB.name,
        "tickets": await list_tickets(),
        "cash": await cash(),
    }
