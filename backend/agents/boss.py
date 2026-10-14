"""Boss: reads each ticket, decides who works on it, and makes the final call."""

from agents.spec import RoleSpec
from models import TicketOutcome

SPEC = RoleSpec(
    name="boss",
    title="Boss",
    prompt_file="boss.md",
    output_type=TicketOutcome,
    mcp_tools=frozenset(
        {"get_ticket", "list_tickets", "get_cash_position", "list_payment_requests", "update_ticket"}
    ),
    can_delegate_to=("inventory", "accounting", "facilities", "customer_service"),
    description="Reads tickets, routes work, makes the final call and sets the ticket status.",
)
