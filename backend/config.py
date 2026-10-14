"""Settings for the agent team: model, MCP connection, and the limits that cap token use."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai import UsageLimits
from pydantic_ai.models.openai import OpenAIResponsesModelSettings

BACKEND_DIR = Path(__file__).resolve().parent
HW_DIR = BACKEND_DIR.parent
DATA_DIR = HW_DIR / "data"
ORIGINAL_DB = DATA_DIR / "campus_customs.db"  # never written
WORKING_DB = DATA_DIR / "campus_customs_new.db"  # what the MCP server reads and writes
MCP_SERVER_SCRIPT = HW_DIR / "mcp_server" / "server.py"

# API key: first match wins (backend/.env, HW 5/.env, then the course folder's shared .env).
for env_file in (BACKEND_DIR / ".env", HW_DIR / ".env", HW_DIR.parent / ".env"):
    load_dotenv(env_file)

# Every agent uses this one model, through the Portkey gateway (OpenAI-compatible).
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1")
REQUEST_TIMEOUT = 90  # seconds per model call

# ---- Limits that keep token use (and runaway loops) in check -------------------------
# One budget per ticket, shared by Boss and every teammate it delegates to.
TICKET_LIMITS = UsageLimits(
    request_limit=36,  # model calls across the whole delegation tree
    tool_calls_limit=60,  # MCP + delegate calls across the tree
    total_tokens_limit=400_000,  # input + output tokens across the tree
)
MAX_DELEGATION_DEPTH = 2  # Boss (0) -> teammate (1) -> teammate (2); depth 2 cannot delegate
MAX_DELEGATIONS_PER_TICKET = 8
# max_tokens covers hidden reasoning + the visible answer; low reasoning effort keeps both small.
MODEL_SETTINGS = OpenAIResponsesModelSettings(
    max_tokens=8000, timeout=REQUEST_TIMEOUT, openai_reasoning_effort="low"
)
# Used once if a run hits max_tokens before answering: no reasoning, just write the output.
FINALIZE_SETTINGS = OpenAIResponsesModelSettings(
    max_tokens=4000, timeout=REQUEST_TIMEOUT, openai_reasoning_effort="none"
)
TOOL_RETRIES = 2  # a tool error is shown to the model at most this many times
MCP_TIMEOUT = 30  # seconds for any single MCP tool call


def mcp_server_env() -> dict[str, str]:
    """Minimal environment for the MCP subprocess: agent role, working DB, no API keys."""
    keep = ("SYSTEMROOT", "PATH", "TEMP", "TMP", "PATHEXT", "COMSPEC")
    env = {k: os.environ[k] for k in keep if k in os.environ}
    env["CAMPUS_CUSTOMS_MCP_ROLE"] = "agent"  # payment approval tools are not even registered
    env["CAMPUS_CUSTOMS_DB"] = str(WORKING_DB)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


PYTHON = sys.executable
