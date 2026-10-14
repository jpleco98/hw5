# Campus Customs MCP Server

**What it's for.** This is the single toolbox shared by the whole Campus Customs operations team: Boss, Inventory, Accounting, Facilities and Customer Service. Agents never touch SQLite directly. They call these tools, so every number they use (stock, prices, lead times, invoices, rent, cash) comes from the database. The tools also enforce the shop rules: payments need a human, balances never go negative, and drafts are never sent. The server is built with [FastMCP](https://gofastmcp.com).

**Which database.** The server uses `data/campus_customs_new.db`, which is the working copy. The original `data/campus_customs.db` is never opened here. It is only used to reset the working copy before a full run (`backend/reset_db.py`, or `run_tickets.py --reset`). To point the server at another copy, set `CAMPUS_CUSTOMS_DB`.

"Today" for every date check is `desk.date_today` (2026-08-31), not the computer's clock.

**Roles.** `CAMPUS_CUSTOMS_MCP_ROLE` decides which tools exist:
- `agent` (the default, and what the backend uses): the 12 tools below. **No tool can move money.**
- `operator` (the human approver, used by the dashboard later): the same 12 tools plus `approve_and_pay` and `reject_payment_request`.

## Tools

### Read tools (read-only connection)
| Tool | Tables | What it returns |
|---|---|---|
| `check_stock(sku, size?, qty_needed?)` | `inventory` | Units on hand and aisle per size. With a size and quantity, it also returns `on_hand`, `shortfall` and `can_fill_now`. |
| `get_vendor_status(vendor_id?)` | `vendors`, `invoices`, `desk` | Specialty, `lead_days`, open invoices with days overdue, `can_ship_new_product` (false while any invoice is unpaid), and the arrival date if ordered today. |
| `get_rent_status(lease_id)` | `leases`, `desk`, `cash_accounts` | Rent, next due date, days until due, overdue or not, cash balances, and whether cash covers the rent. |
| `list_tickets(status?)` | `tickets` | The ticket board, optionally filtered by status. |
| `get_ticket(ticket_id)` | `tickets`, `invoices`, `vendors`, `leases`, `desk`, `ticket_updates`, `drafts`, `payment_requests` | One ticket with its linked invoice and lease, and everything the team has already done on it. |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | Amount, due date, status, days overdue, and whether it is blocking the vendor. |
| `quote_bulk_price(sku, qty, discount_pct)` | `pricing` | Discounted unit price, unit and order margin, margin %, `below_cost`, and the break-even discount. |
| `get_cash_position()` | `cash_accounts`, `payment_requests`, `payments`, `desk` | Balances, pending requests and their total, `cash_after_pending`, and payments already made. |
| `list_payment_requests(status?)` | `payment_requests` | Requests that are pending, paid or rejected. |

### Board write tools (agents; these never move money)
| Tool | Tables | What it does |
|---|---|---|
| `update_ticket(ticket_id, status, note, agent)` | `tickets`, `ticket_updates` | Sets the ticket status and adds a note to the ticket's history explaining why. |
| `save_draft(ticket_id, audience, recipient, subject, body, author)` | `drafts` | Saves a customer, vendor, landlord or internal message as a **draft**. Nothing is sent. |
| `request_payment(ticket_id, kind, reason, requested_by, invoice_id \| lease_id \| vendor_id+sku+size+qty)` | `payment_requests` (checks `invoices`, `leases`, `vendors`, `inventory`, `pricing`) | Puts an invoice, rent or purchase-order payment on the board for **human approval**. The amount comes from the database, and duplicates are reused instead of created again. |

### Human operator tools (only when `CAMPUS_CUSTOMS_MCP_ROLE=operator`)
| Tool | Tables | What it does |
|---|---|---|
| `approve_and_pay(request_id, approved_by, account="checking")` | `payment_requests`, `payments`, `cash_accounts`, `invoices` / `leases`, `ticket_updates` | Approves a request and pays it in one all-or-nothing step. **It refuses** if cash is short (so no negative balances), if the invoice isn't open, if a purchase-order vendor still has an open invoice, or if `approved_by` is an agent's name. When it pays, it records the payment, lowers the cash balance, marks the invoice paid or moves the lease's `next_due` forward a month, and sets the expected arrival date for a purchase order. |
| `reject_payment_request(request_id, rejected_by, reason)` | `payment_requests`, `ticket_updates` | Rejects a request. No money moves. |

**Board tables.** `payment_requests`, `drafts` and `ticket_updates` are created on first use, only in the working copy. A reset removes them along with everything else.

## Run and test

```bash
# from the repo root, with the .venv activated
pip install -r requirements.txt
python mcp_server/server.py          # stdio, agent role
python mcp_server/test_server.py     # offline rule checks on a temp copy of the original DB
```

The FastAPI backend starts its own copies of this server, so you only run it by hand to connect an MCP client such as Claude Code. Claude Code reads `.mcp.json` from the repo root.
