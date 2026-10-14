"""Accounting: watches cash and invoices, checks margins, prepares payments/POs for human approval."""

from agents.spec import RoleSpec
from models import AgentReport

SPEC = RoleSpec(
    name="accounting",
    title="Accounting",
    prompt_file="accounting.md",
    output_type=AgentReport,
    mcp_tools=frozenset(
        {
            "get_ticket",
            "get_cash_position",
            "get_invoice",
            "get_vendor_status",
            "get_rent_status",
            "quote_bulk_price",
            "list_payment_requests",
            "request_payment",
        }
    ),
    can_delegate_to=("boss", "inventory", "facilities", "customer_service"),
    description="Cash, invoices, margins and discounts; creates payment requests that wait for a human.",
)
