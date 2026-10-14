"""Inventory: checks stock by SKU and size, spots shortfalls, finds which vendor can restock."""

from agents.spec import RoleSpec
from models import AgentReport

SPEC = RoleSpec(
    name="inventory",
    title="Inventory",
    prompt_file="inventory.md",
    output_type=AgentReport,
    mcp_tools=frozenset({"get_ticket", "check_stock", "get_vendor_status", "quote_bulk_price"}),
    can_delegate_to=("boss", "accounting", "facilities", "customer_service"),
    description="Stock by SKU/size, shortfalls, which vendor can restock, lead times, blocked vendors.",
)
