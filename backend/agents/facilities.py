"""Facilities: the shop space side (lease, rent, landlord)."""

from agents.spec import RoleSpec
from models import AgentReport

SPEC = RoleSpec(
    name="facilities",
    title="Facilities",
    prompt_file="facilities.md",
    output_type=AgentReport,
    mcp_tools=frozenset({"get_ticket", "get_rent_status", "get_cash_position", "save_draft"}),
    can_delegate_to=("boss", "inventory", "accounting", "customer_service"),
    description="Lease, rent amount and due date, landlord notes (drafts only).",
)
