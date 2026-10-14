"""Customer Service: drafts messages for customers (drafts stay on the board, never sent)."""

from agents.spec import RoleSpec
from models import AgentReport

SPEC = RoleSpec(
    name="customer_service",
    title="Customer Service",
    prompt_file="customer_service.md",
    output_type=AgentReport,
    mcp_tools=frozenset({"get_ticket", "check_stock", "save_draft"}),
    can_delegate_to=("boss", "inventory", "accounting", "facilities"),
    description="Drafts customer and student-group messages from the team's decision (never sends).",
)
