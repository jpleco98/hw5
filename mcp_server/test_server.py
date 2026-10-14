"""Offline test of the MCP tools against a throwaway copy of the ORIGINAL database.

It never touches data/campus_customs_new.db. It runs the real FastMCP server
in-process (operator role, so the human-only payment tools are present) and
checks the shop rules: the amounts come from the database, payments need a human,
the pay tool refuses when cash is short, and the right tables get updated.

Run from HW 5/:  .venv\\Scripts\\python mcp_server\\test_server.py
"""

import asyncio
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp()) / "test.db"
shutil.copy(HERE.parent / "data" / "campus_customs.db", TMP)
os.environ["CAMPUS_CUSTOMS_DB"] = str(TMP)
os.environ["CAMPUS_CUSTOMS_MCP_ROLE"] = "operator"
sys.path.insert(0, str(HERE))

from fastmcp import Client  # noqa: E402

import server  # noqa: E402


async def call(c, name, **args):
    r = await c.call_tool(name, args, raise_on_error=False)
    return (r.content[0].text, True) if r.is_error else (r.structured_content, False)


def db(sql):
    with sqlite3.connect(TMP) as conn:
        return conn.execute(sql).fetchall()


async def main():
    async with Client(server.mcp) as c:
        names = sorted(t.name for t in await c.list_tools())
        print("tools:", names)

        q, _ = await call(c, "quote_bulk_price", sku="CC-HOOD-NAVY", qty=20, discount_pct=15)
        assert q["unit_price"] == 49.3 and q["unit_margin"] == 27.3, q
        print("quote 20 hoodies @15% off:", q["unit_price"], "margin", q["order_margin"])

        r1, _ = await call(c, "request_payment", ticket_id=101, kind="invoice", invoice_id=501,
                           reason="test", requested_by="accounting")
        r2, _ = await call(c, "request_payment", ticket_id=102, kind="rent", lease_id=1,
                           reason="test", requested_by="accounting")
        r3, _ = await call(c, "request_payment", ticket_id=103, kind="purchase_order", vendor_id=1,
                           sku="CC-HOOD-NAVY", size="M", qty=12, reason="test", requested_by="accounting")
        dup, _ = await call(c, "request_payment", ticket_id=101, kind="invoice", invoice_id=501,
                            reason="again", requested_by="accounting")
        assert (r1["amount"], r2["amount"], r3["amount"]) == (840.0, 2400.0, 264.0)
        assert dup["request_id"] == r1["request_id"], "duplicate request should be reused"
        assert db("SELECT count(*) FROM payments") == [(0,)], "requesting must not pay"
        print("requests:", r1["amount"], r2["amount"], r3["amount"], "- no payments yet")

        msg, err = await call(c, "approve_and_pay", request_id=r3["request_id"], approved_by="Juan")
        assert err and "open invoice" in msg, msg
        print("PO blocked while #501 open:", msg[:70], "...")

        msg, err = await call(c, "approve_and_pay", request_id=r1["request_id"], approved_by="accounting")
        assert err and "human" in msg, msg

        p1, _ = await call(c, "approve_and_pay", request_id=r1["request_id"], approved_by="Juan")
        p2, _ = await call(c, "approve_and_pay", request_id=r2["request_id"], approved_by="Juan")
        assert p2["account_balance_after"] == 160.0, p2
        assert db("SELECT status FROM invoices WHERE id=501") == [("paid",)]
        assert db("SELECT next_due FROM leases WHERE id=1") == [("2026-10-02",)]
        print("paid #501 and rent -> balance", p2["account_balance_after"], "| tables:", p2["tables_updated"])

        msg, err = await call(c, "approve_and_pay", request_id=r3["request_id"], approved_by="Juan")
        assert err and "negative" in msg, msg
        assert db("SELECT balance FROM cash_accounts") == [(160.0,)]
        print("PO $264 refused with $160 left:", msg[:60], "...")

        d, _ = await call(c, "save_draft", ticket_id=101, audience="customer", recipient="Tauhid Zaman",
                          subject="Your tee", body="Hi", author="customer_service")
        t, _ = await call(c, "update_ticket", ticket_id=101, status="waiting_on_vendor",
                          note="test", agent="boss")
        assert d["status"] == "draft" and t["status"] == "waiting_on_vendor" and len(t["drafts"]) == 1
        print("draft + ticket update ok; history:", [u["agent"] for u in t["updates"]])

        pos, _ = await call(c, "get_cash_position")
        print("cash position:", pos["total_cash"], "pending:", pos["pending_total"],
              "payments:", len(pos["payments_made"]))
    print("ALL CHECKS PASSED")


asyncio.run(main())
