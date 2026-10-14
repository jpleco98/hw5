# HW5 — Harness Design Notes

Design write-up for **Campus Customs Multi-Agent Operations**. A team of agents (Boss, Inventory, Accounting, Facilities and Customer Service) resolves the tickets on the shop's board. The system has three parts: an MCP server, a FastAPI backend that runs the agents, and a React dashboard where a human watches the work and approves payments. The **System overview** below describes the finished system. After it comes one section per problem, showing how each part was built and tested.

---

## System overview (final, Problem 9)

> Start here. This section is the reference for the finished system: tables, MCP tools, the five agents, API routes, the dashboard and the safety rules.

### How to run it
| Part | Command (from the folder shown) | URL |
|---|---|---|
| Python deps | `HW 5`: `.venv\Scripts\python -m pip install -r requirements.txt` (fastmcp, pydantic-ai-slim[openai,mcp], python-dotenv, fastapi, uvicorn) | |
| Backend + agents | `HW 5/backend`: `..\.venv\Scripts\activate`, then `uvicorn main:app --reload --port 8000` | http://localhost:8000/docs |
| Dashboard | `HW 5/frontend`: `npm install` (first time), then `npm run dev` | http://localhost:5173 |
| Full run from the terminal | `HW 5/backend`: `..\.venv\Scripts\python run_tickets.py --all --reset` | |
| Reset the board | dashboard **Start a fresh day**, `POST /api/reset`, or `python reset_db.py` | |
| MCP rule tests (offline, no key) | `HW 5`: `.venv\Scripts\python mcp_server\test_server.py` | |
| API key | `PORTKEY_API_KEY` in the course folder's `.env` (or `HW 5/.env`, `backend/.env`) | |

### Architecture
```
React desk (frontend/, :5173) ──HTTP/CORS──► FastAPI (backend/main.py, :8000)
   rail · corkboard · drawer                   │                     │
   polls /api/events, /api/tickets, /api/cash  │ human routes        │ POST /tickets/{id}/run
                                               ▼                     ▼
                                operator MCP client          Team (backend/team.py)
                                (approve / reject)           Boss ⇄ Inventory ⇄ Accounting ⇄ Facilities ⇄ Customer Service
                                               │             (gpt-6-luna via Portkey; delegate() between any two)
                                               │                     │ agent MCP client (no money tools)
                                               ▼                     ▼
                                     mcp_server/server.py (FastMCP) ──► data/campus_customs_new.db
                                                                     (data/campus_customs.db = untouched original)
   every agent-loop step ──append──► output/audit_trail.json
```

### Tables (database: `data/campus_customs_new.db`)
| Table | Fields | Why it matters to the agents |
|---|---|---|
| `desk` | date_today, notes | The shop's "today" (2026-08-31). Every overdue and due-soon check uses it. |
| `tickets` | id, type, requester, subject, sku, size, qty, lease_id, invoice_id, status, notes, created_at | The work queue. Boss reads it, and agents set the status. |
| `inventory` | sku, name, size, qty, location | Stock by SKU and size, and shortfalls. |
| `pricing` | sku, unit_cost, list_price | Margins, discount floors and restock cost. |
| `vendors` | id, name, specialty, lead_days | Who restocks what, and how fast. |
| `invoices` | id, vendor_id, amount, due_date, status, description | What we owe. An open invoice blocks that vendor. |
| `leases` | id, space_name, landlord, monthly_rent, next_due, notes | Rent and its due date. Facilities owns it. |
| `cash_accounts` | name, balance, date | The only money. It must never go negative. |
| `payments` | id, kind, ref_id, amount, account, paid_at, approved_by | Every payment, with the human who approved it. |
| *board:* `payment_requests` | id, ticket_id, kind, ref_id, vendor_id, sku, size, qty, amount, reason, requested_by, status, decided_by, payment_id, expected_arrival, … | Checks the agents prepare and a human decides on. |
| *board:* `drafts` | id, ticket_id, audience, recipient, subject, body, author, status | Customer, vendor or landlord messages, never sent. |
| *board:* `ticket_updates` | id, ticket_id, agent, status, note, shop_date | The history of decisions and status changes. |

The board tables are created by the MCP server in the working copy only. A reset removes them.

### MCP tools (`mcp_server/server.py`, server `campus-customs-ops`)
| Tool | Tables | Who can call it |
|---|---|---|
| `check_stock` | inventory | Inventory, Customer Service |
| `get_vendor_status` | vendors, invoices, desk | Inventory, Accounting |
| `get_rent_status` | leases, desk, cash_accounts | Facilities, Accounting |
| `list_tickets` | tickets | Boss |
| `get_ticket` | tickets, invoices, vendors, leases, desk, ticket_updates, drafts, payment_requests | all five |
| `get_invoice` | invoices, vendors, desk | Accounting |
| `quote_bulk_price` | pricing | Accounting, Inventory |
| `get_cash_position` | cash_accounts, payment_requests, payments, desk | Boss, Accounting, Facilities |
| `list_payment_requests` | payment_requests | Boss, Accounting |
| `update_ticket` | tickets, ticket_updates | Boss |
| `save_draft` | drafts | Customer Service, Facilities |
| `request_payment` | payment_requests (validated against invoices, leases, vendors, inventory, pricing) | Accounting |
| `approve_and_pay` | payment_requests, payments, cash_accounts, invoices, leases, vendors, ticket_updates | **human only** (operator role, used by the approve route) |
| `reject_payment_request` | payment_requests, ticket_updates | **human only** |

The read tools open the database read-only. Write tools run in a single transaction that either fully succeeds or changes nothing.

### The five agents (`backend/agents/*.py`, prompts in `backend/prompts/*.md`, all `gpt-6-luna`)
| Agent | Job | Output | Writes |
|---|---|---|---|
| **Boss** | Reads the ticket, picks who to call, makes the final call, sets the status | `TicketOutcome` | `update_ticket` |
| **Inventory** | Stock by SKU and size, shortfalls, vendor match by specialty, blocked vendors, lead times | `AgentReport` | none |
| **Accounting** | Cash, invoices, margins and discount quotes; prepares payments and purchase orders for a human | `AgentReport` | `request_payment` |
| **Facilities** | Checks the lease and rent against what the landlord says | `AgentReport` | `save_draft` (landlord) |
| **Customer Service** | Drafts customer messages from the team's decision | `AgentReport` | `save_draft` (customer) |

**Delegation:** every agent has `delegate(to, task)` and can reach any of the other four. The guardrails are: no self-delegation, no loops back up the chain, depth ≤ 2, and at most 8 delegations per ticket.

**Loop:** each agent run is driven step by step with `agent.iter()`, and **every step is appended** to `output/audit_trail.json`. That covers who acted, the run tree, the model's text, tool calls with arguments, results, and token use.

**Recovery:** if a run uses up its reply budget before answering, it is finished once by a tool-less twin with reasoning turned off, logged as `run_retry`.

### API routes (`backend/main.py`, http://localhost:8000)
| Method | URL | What it does |
|---|---|---|
| GET | `/api/tickets` | Tickets with board status, `state` (open, running or resolved), pending approvals, and Boss's last note |
| GET | `/api/tickets/{id}` | One ticket with its linked invoice and lease, history, drafts and requests |
| POST | `/api/tickets/{id}/run` | Runs the agent team on the ticket (job id, or `?wait=true` for the outcome) |
| GET | `/api/runs`, `/api/runs/{job_id}` | Status and outcome of agent runs |
| GET | `/api/events?since=` | Recent agent events (who, what they said, tools, hand-offs) for live refresh |
| GET | `/api/payment-requests` | Checks waiting for a human, with the payee |
| POST | `/api/payment-requests/{id}/approve` | **Human approval: the only route that changes cash.** It refuses with 409 if cash is short, the vendor is blocked, or the request isn't pending. |
| POST | `/api/payment-requests/{id}/reject` | Human rejects a request. No money moves. |
| GET | `/api/cash` | Checking balance from `cash_accounts`, plus pending and paid amounts |
| POST | `/api/reset` | Resets the working database from the original |
| GET | `/api/health` | Server, model and agent readiness |

### Dashboard (`frontend/`, design rationale in `output/design.md`)
- **Ticket rail** (left): paper slips that pick up a RESOLVED stamp and status pills.
- **Corkboard** (center): the five agents around a corkboard, each showing a live human verb, its tool arguments and a speech bubble. Hand-offs are red string.
- **Transcript and debrief**: each agent writes in its own voice (memo, stock tag, ledger, blueprint, letter). A replay slider rebuilds any finished run step by step.
- **Cash drawer** (right): a rolling-counter checking balance, a runway bar, **checks to sign** (the amount spelled out in words and a typed signature are needed before Sign & pay is enabled), and a register tape of payments.

### Safety rules (enforced in code, not only in prompts)
1. **Humans approve money.** Agents can only *request* payments. The pay tool isn't even registered on the agents' MCP connection, and it rejects an agent name as the approver.
2. **No negative balances.** The pay tool refuses any amount larger than the balance, all in one transaction. Amounts always come from the database, never from the model.
3. **Vendor block.** A vendor with an open invoice can't be paid for a new purchase order. `can_ship_new_product` is calculated from `invoices`.
4. **The shop date** comes from `desk.date_today`, never the computer's clock.
5. **Least privilege.** Each agent has its own MCP tool list. The harness stamps the identity field and the ticket id on every write, so an agent can't act under another name or touch a different ticket.
6. **Nothing is sent.** Customer, vendor and landlord messages are drafts. There is no email or phone tool.
7. **Prompt injection:** ticket notes are treated as data, never as instructions.
8. **Secrets:** the API key is loaded from `.env`, and the MCP subprocess gets no keys.
9. **Audit and reset:** an append-only audit trail, plus a reset from the untouched original.
10. **Token limits:** per ticket, 36 model requests, 60 tool calls and 400k tokens (shared across the whole delegation tree). Each model call is capped at 8,000 output tokens with low reasoning effort, and timeouts apply to model and MCP calls.

### Final full run (Problem 9)
After a reset: **$3,400.00 → −$840.00 (invoice #501, ticket 101) → −$2,400.00 (rent, ticket 102) → $0 (ticket 103) = $160.00**. That equals `cash_accounts.checking`, and both payments were approved by Juan Pablo. The details are in `output/desk_tickets.html` (Cash tab), `output/resolved_tickets.json` and `output/resolved_board.html`.

---

## Problem 2 — The Campus Customs Database

### Original vs. working copy
| File | Role |
|---|---|
| `data/campus_customs.db` | The **original**. Nothing writes to it. It is only used to reset the working copy. |
| `data/campus_customs_new.db` | The **working copy**, made by copying the original. The MCP server and backend read and write only this file. Before every full ticket-resolution run it gets reset with another copy of the original. |

The database is SQLite and has 9 tables. The only declared foreign keys are `tickets.lease_id → leases.id`, `tickets.invoice_id → invoices.id` and `invoices.vendor_id → vendors.id`. SQLite leaves foreign-key checks off unless a connection turns them on, and every other link is just matching values (for example `tickets.sku` to `inventory.sku`). So our tools have to check those links themselves.

### Tables

#### `desk` (1 row): the shop's clock
| Field | Type | Meaning |
|---|---|---|
| `date_today` | TEXT (ISO date) | "Today" for the shop: **2026-08-31** |
| `notes` | TEXT, nullable | Free-form desk note (currently empty) |

**Why it matters:** every agent judges "overdue" and "due soon" against `date_today`, never the computer's clock. Delivery dates are `date_today + vendors.lead_days`.

#### `tickets` (3 rows): the work queue on the board
| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Ticket number (101–103) |
| `type` | TEXT | `customer_order`, `rent_notice` or `price_override`. This tells Boss which specialists to route the ticket to. |
| `requester` | TEXT | Who asked: a customer, the landlord or a student org |
| `subject` | TEXT | Short title for the board |
| `sku`, `size`, `qty` | TEXT / TEXT / INTEGER, nullable | What product is involved and how many. Links by value to `inventory` and `pricing`. |
| `lease_id` | INTEGER FK → `leases.id`, nullable | Set on rent tickets |
| `invoice_id` | INTEGER FK → `invoices.id`, nullable | The vendor invoice tied to this ticket |
| `status` | TEXT | All are `open` now. The agents move tickets toward resolved. |
| `notes` | TEXT | The requester's message in plain words |
| `created_at` | TEXT (ISO datetime, −04:00) | When the ticket landed |

**Why it matters:** it's the input to the whole system. Boss reads each row and the agents work it until it is closed.

#### `inventory` (10 rows): stock by SKU and size
| Field | Type | Meaning |
|---|---|---|
| `sku` | TEXT, PK part | Product code (`CC-HOOD-NAVY`, `CC-TEE-WHITE`, `CC-HAT-BLUE`, `CC-MUG-CREST`) |
| `name` | TEXT | Product name |
| `size` | TEXT, PK part | `S`/`M`/`L`/`XL`, or `OS` (one size) |
| `qty` | INTEGER | Units on hand |
| `location` | TEXT | Aisle where it sits |

**Why it matters:** Inventory checks `qty` against what a ticket asks for to find shortfalls. Two rows are already at 0: Tee S and Crest Mug OS.

#### `pricing` (4 rows): cost and price per SKU
| Field | Type | Meaning |
|---|---|---|
| `sku` | TEXT PK | Product code |
| `unit_cost` | REAL | What the shop pays per unit |
| `list_price` | REAL | Normal selling price |

**Why it matters:** Accounting uses these to compute margins (Hoodie $58 − $22 = $36, 62%). It decides how deep a discount can go and what a restock order would cost (`qty × unit_cost`).

#### `vendors` (3 rows): who can restock, and how fast
| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Vendor id |
| `name` | TEXT | Bulldog Print Co / Elm City Gifts / QuickShip CT |
| `specialty` | TEXT | `apparel reprint` / `mugs and small goods` / `local courier` |
| `lead_days` | INTEGER | Days to deliver: 5 / 3 / 1 |

**Why it matters:** Inventory matches a SKU to a vendor through `specialty`, since there is no SKU→vendor column. The lead time comes only from `lead_days`.

#### `invoices` (1 row): what the shop owes vendors
| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Invoice number |
| `vendor_id` | INTEGER FK → `vendors.id` | Who is owed |
| `amount` | REAL | Amount owed |
| `due_date` | TEXT (ISO date) | Overdue when earlier than `desk.date_today` |
| `status` | TEXT | `open` (unpaid) → `paid` |
| `description` | TEXT | What it was for |

**Why it matters:** this table drives the **blocking rule**. A vendor with an `open` invoice ships nothing new. It is also the main thing Accounting pays.

#### `leases` (1 row): the shop space
| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Lease id |
| `space_name` | TEXT | Chapel Street shop |
| `landlord` | TEXT | Elm City Properties |
| `monthly_rent` | REAL | $2,400 |
| `next_due` | TEXT (ISO date) | 2026-09-02 |
| `notes` | TEXT, nullable | Free-form |

**Why it matters:** Facilities owns this table. After rent is paid, `next_due` should move forward one month so the lease doesn't still look due.

#### `cash_accounts` (1 row): the only source of money
| Field | Type | Meaning |
|---|---|---|
| `name` | TEXT PK | `checking` |
| `balance` | REAL | **$3,400.00** |
| `date` | TEXT (ISO date) | Date the balance was last updated |

**Why it matters:** every payment comes out of here. The pay tool refuses any payment larger than `balance`, so it can never go negative. No revenue is modeled, so the balance only goes down.

#### `payments` (0 rows): record of money paid out
| Field | Type | Meaning |
|---|---|---|
| `id` | INTEGER PK | Payment id |
| `kind` | TEXT | What was paid, e.g. `invoice`, `rent`, `purchase_order` |
| `ref_id` | INTEGER, nullable | The id of the paid thing (`invoices.id`, `leases.id`, …) |
| `amount` | REAL | Amount paid |
| `account` | TEXT | Which `cash_accounts.name` it came from |
| `paid_at` | TEXT | Shop date of the payment |
| `approved_by` | TEXT, NOT NULL | The **human** who approved it |

**Why it matters:** every payment leaves a row here. `approved_by` is required, which matches the rule that no money moves without human approval.

### The three open tickets and how they link
```
desk.date_today = 2026-08-31          cash_accounts.checking = $3,400

#101 customer_order  ──sku/size──► inventory CC-TEE-WHITE S  qty 0  (short 1)
  Tauhid Zaman       ──invoice_id─► invoices 501  $840  due 08-28  OPEN → overdue 3 days
  tee S × 1                           └─vendor_id─► vendors 1 Bulldog Print Co (apparel reprint, 5 days)

#102 rent_notice     ──lease_id──► leases 1 Chapel Street shop  $2,400  next_due 09-02 (2 days, not overdue)
  Elm City Properties

#103 price_override  ──sku/size──► inventory CC-HOOD-NAVY M  qty 8  (short 12 of 20)
  Yale AI Club       ──sku──────► pricing  cost $22 / list $58
  hoodie M × 20, bulk discount       restock would also come from Bulldog Print Co (apparel)
```

- **#101 (Bulldog tee, size S):** stock is 0. The vendor for this reprint is Bulldog Print Co, but its invoice #501 ($840) is unpaid and past due (due 08-28, today is 08-31). Under the blocking rule, nothing ships until #501 is paid. The steps are: Accounting prepares the $840 payment, a human approves it, then the reprint is ordered and arrives about 5 days later (around 09-05). Customer Service drafts a note to Tauhid with that timing.
- **#102 (rent):** $2,400 is due 09-02. That's not overdue yet, but it's two days away. Facilities and Accounting prepare the payment for human approval. Once it's paid, `leases.next_due` moves to 10-02.
- **#103 (bulk hoodie discount):** 20 × size M is asked for but only 8 are on hand, so 12 are short. Restocking is also blocked by invoice #501, since hoodies come from the same apparel vendor. At list price the margin is $36 a unit, so Accounting can propose a discount that keeps a healthy margin. Boss makes the final call, and Customer Service drafts the reply.

**Cash check:** paying #501 ($840) and the rent ($2,400) uses $3,240 of the $3,400, which leaves **$160**. Reprinting the 12 hoodies would cost 12 × $22 = **$264** at unit cost. So the shop can't pay all three right now, and the agents have to choose an order of priority. The pay tool's refusal is what prevents a negative balance.

---

## Problem 3 — The MCP Server

`mcp_server/server.py` is a FastMCP server named `campus-customs-ops`. It's the one toolbox every agent uses, and it only talks to the working copy `data/campus_customs_new.db`. All three tools open the database **read-only**, so they can look but never change anything. Each tool returns a typed Pydantic model, so agents get named fields rather than prose. If you pass an unknown SKU, size, vendor or lease, the tool returns an error that lists the valid values, so an agent can't build on made-up data. Every date calculation uses `desk.date_today`. See `mcp_server/README.md` for how to run it.

### Tool 1: `check_stock(sku, size?, qty_needed?)`
- **Reads:** `inventory` (sku, name, size, qty, location).
- **Returns:** units on hand and aisle for every size, the total, and, when a size and quantity are given, `on_hand`, `shortfall` and `can_fill_now`.
- **Unlocks ticket 103** (also used on 101).
- **Why it's the right tool:** the Yale AI Club wants 20 size-M hoodies, and only this tool can say `on_hand 8, shortfall 12`, which tells Boss whether to offer the 8 now or plan a 12-unit reprint before agreeing to any price.
- **Also on 101:** the same call returns `on_hand 0, shortfall 1` for the tee in size S, which proves Tauhid's order has to wait for a restock.

### Tool 2: `get_vendor_status(vendor_id?)`
- **Reads:** `vendors` (name, specialty, lead_days), `invoices` (open rows per vendor: amount, due_date, description) and `desk.date_today`.
- **Returns:** for each vendor, its open invoices with `days_overdue`, `open_balance`, `can_ship_new_product`, a `block_reason`, and `arrival_if_ordered_today`.
- **Unlocks ticket 101** (and the restock half of 103).
- **Why it's the right tool:** ticket 101 points at invoice #501, and this tool shows it's an $840 bill from Bulldog Print Co (the only apparel vendor), 3 days overdue as of 2026-08-31, which sets `can_ship_new_product = false`, so the tee reprint is blocked until a human approves paying #501.
- **Also:** after payment the reprint takes 5 days (`lead_days`), which is the date Customer Service will quote. Hoodies come from the same vendor, so ticket 103's 12-unit restock hits the same block.

### Tool 3: `get_rent_status(lease_id)`
- **Reads:** `leases` (space_name, landlord, monthly_rent, next_due, notes), `desk.date_today` and `cash_accounts` (balances).
- **Returns:** `monthly_rent`, `next_due`, `days_until_due`, `is_overdue`, the cash balances and `can_cover_rent`.
- **Unlocks ticket 102.**
- **Why it's the right tool:** the landlord's email only claims "rent due in 2 days", and this tool checks it against lease #1 ($2,400 due 2026-09-02, `days_until_due 2`, not overdue) and confirms checking ($3,400) can cover it, so Facilities hands Accounting a verified amount for a payment a human then approves.
- **Also:** the tool itself pays nothing.

### Design choices
- **Read-only first.** Problem 3's tools only look things up. Payments get their own write tools later, with a human-approval gate and a refusal when cash is short, so a lookup tool can never move money by accident.
- **Vendor matching uses `specialty`.** No column links a SKU to a vendor, so the tool returns `specialty` and lets the agent match it ("apparel reprint" for tees and hoodies) rather than inventing a hidden mapping.
- **The blocking rule lives in the tool.** `can_ship_new_product` is calculated from the `invoices` table, so no agent can forget the rule that a vendor won't ship while an invoice is unpaid.
- **Tested in memory** with FastMCP's `Client(mcp)` against the working copy. Results matched the database (tee S short 1, hoodie M short 12, vendor 1 blocked by #501 at 3 days overdue, rent due in 2 days). Unknown SKUs, sizes and leases returned errors. The working copy's hash didn't change, which confirms the tools are read-only.

---

## Problem 4 — Connecting the MCP Server to the Vibe Coder

**Connection.** Claude Code reads the project-scoped `.mcp.json`, which registers the server as `campus-customs-ops` over stdio. It launches the server with the HW5 venv's Python:
- `AI foundations BC/.mcp.json`: the copy Claude Code actually loads, because the session runs from the course folder. Its paths are `HW 5/.venv/Scripts/python.exe` and `HW 5/mcp_server/server.py`.
- `HW 5/.mcp.json`: the same entry with paths relative to `HW 5/`, for opening the project straight from that folder.

The server appeared only after the session restarted, because `.mcp.json` is read at startup. After that its three tools showed up as `mcp__campus-customs-ops__*` and were called live.

**Smoke test (`output/mcp_smoke.json`).** There was one natural-language prompt per tool, and every output was checked against `data/campus_customs_new.db`:

| Prompt | Tool | Key result | Matches DB |
|---|---|---|---|
| "…can we fill ticket 101" | `check_stock(CC-TEE-WHITE, S, 1)` | S on hand 0, shortfall 1, can't fill | yes (`inventory`) |
| "…why we can't restock the tee" | `get_vendor_status()` | Bulldog Print Co blocked by #501, $840, 3 days overdue; lead 5 days | yes (`vendors`, `invoices`, `desk`) |
| "…if ticket 102 rent is overdue" | `get_rent_status(1)` | $2,400 due 2026-09-02, 2 days out, not overdue; checking $3,400 covers it | yes (`leases`, `cash_accounts`, `desk`) |

Each entry stores the prompt, the tool name, the arguments and where each one came from in the ticket row, the raw tool output, and a `db_check` with the SQL, the rows it returned, and any derived arithmetic (days overdue, arrival dates). All three tools are read-only, so the working copy was unchanged by the test.

---

## Problem 5 — The Agent Team and the Grown MCP Server

### Layout
```
backend/
  config.py              model (gpt-6-luna via Portkey), MCP launch settings, all limits
  models.py              data types: TeamDeps, AgentReport, TicketOutcome, AuditEntry, ...
  team.py                builds the 5 agents, the shared MCP connection, delegate(), the audited agent loop
  audit.py               append-only writer for output/audit_trail.json
  agents/                one file per role (RoleSpec: prompt, output type, MCP tool allow-list, delegates)
    boss.py  inventory.py  accounting.py  facilities.py  customer_service.py
  prompts/               one prompt per agent, written as the owner
    boss.md  inventory.md  accounting.md  facilities.md  customer_service.md
  run_tickets.py         CLI: run the team on one/all tickets (--reset for a fresh DB)
  reset_db.py            copy the original DB over the working copy
mcp_server/server.py     the only shop-data layer (12 agent tools + 2 human-only tools)
```

**Model.** Every agent uses `gpt-6-luna` through Portkey (`PORTKEY_API_KEY` from the course `.env`). It runs on the OpenAI **Responses** API, because the gateway rejects function tools combined with reasoning on `/chat/completions` for this model.

**One shop-data layer.** The agents have no Python tools that touch SQLite. Their only data tools are the MCP tools, reached through one shared stdio connection to `mcp_server/server.py` over `data/campus_customs_new.db`. Their only other tool is `delegate`.

### The agents
| Agent | File / prompt | Output | MCP tools it may call | Writes it can make |
|---|---|---|---|---|
| **Boss** | `agents/boss.py` / `prompts/boss.md` | `TicketOutcome` (decision, rationale, status, request ids, draft ids, human next steps, risks) | `get_ticket`, `list_tickets`, `get_cash_position`, `list_payment_requests`, `update_ticket` | Ticket status and notes |
| **Inventory** | `agents/inventory.py` / `prompts/inventory.md` | `AgentReport` | `get_ticket`, `check_stock`, `get_vendor_status`, `quote_bulk_price` | None |
| **Accounting** | `agents/accounting.py` / `prompts/accounting.md` | `AgentReport` | `get_ticket`, `get_cash_position`, `get_invoice`, `get_vendor_status`, `get_rent_status`, `quote_bulk_price`, `list_payment_requests`, `request_payment` | Payment requests (pending, for a human) |
| **Facilities** | `agents/facilities.py` / `prompts/facilities.md` | `AgentReport` | `get_ticket`, `get_rent_status`, `get_cash_position`, `save_draft` | Landlord drafts |
| **Customer Service** | `agents/customer_service.py` / `prompts/customer_service.md` | `AgentReport` | `get_ticket`, `check_stock`, `save_draft` | Customer drafts |

`AgentReport` holds `summary`, `facts` (each with its `source_tool`), `actions_taken`, `payment_request_ids`, `draft_ids`, `recommendation`, `needs_human_approval` and `blockers`. A specialist's report is what the delegating agent gets back, so facts carry their sources up the chain.

**The prompts.** Each prompt is written in the owner's voice and covers:
- the role and its scope (what it does and does not do),
- its exact tools,
- the shop rules it must apply (date, vendor blocking, lead times, human approval, no negative cash, cash only goes out, drafts only, discount policy, cash priorities),
- when to delegate and to whom,
- a step-by-step procedure for each ticket type,
- the output it must return,
- and efficiency rules.

At run time the harness adds a short context block to each prompt: who the agent is, the ticket, the delegation chain, the delegations left, and its tool list.

### Delegation (full connectivity)
Every agent has `delegate(to, task)`, and every agent can name any of the other four. The delegated agent runs its own full loop and returns its report as JSON. Guardrails keep full connectivity from turning into an endless loop:
- No delegating to yourself.
- No delegating back to an agent already in the current chain (for example Boss → Accounting → Boss).
- Maximum depth of 2 (Boss → teammate → teammate). At depth 2 an agent must answer itself.
- At most 8 delegations per ticket.
- A refused delegation returns `REFUSED: …` to the model and is logged as `delegation_refused`.

### Audit trail (`output/audit_trail.json`)
Every agent run is driven step by step with `agent.iter()`, and every step **appends** one `AuditEntry`. The file is never wiped. Writes go to a temp file and then replace the original, so the JSON is always valid.

Fields recorded per step:
- `ts`, `session_id`, `ticket_id`
- `run_id`, `parent_run_id` (rebuilds the delegation tree)
- `agent`, `chain`, `depth`, `step`
- `event`: `run_start`, `model_response`, `tool_results`, `delegation_refused`, `run_end` or `run_error`
- `model`, `prompt`, model `text`
- `tool_calls` (tool, call id, arguments) and `tool_results` (tool, call id, ok/error, output cut to 2,000 characters)
- `step_usage` and `cumulative_usage` (requests, tool calls, input and output tokens for the whole ticket)
- the final `output`, or the `error`

### MCP tools (all of them, with the tables they use)
| Tool | Added in | Tables | Called by |
|---|---|---|---|
| `check_stock` | P3 | `inventory` | Inventory, Customer Service |
| `get_vendor_status` | P3 | `vendors`, `invoices`, `desk` | Inventory, Accounting |
| `get_rent_status` | P3 | `leases`, `desk`, `cash_accounts` | Facilities, Accounting |
| `list_tickets` | P5 | `tickets` | Boss |
| `get_ticket` | P5 | `tickets`, `invoices`, `vendors`, `leases`, `desk`, `ticket_updates`, `drafts`, `payment_requests` | all five |
| `get_invoice` | P5 | `invoices`, `vendors`, `desk` | Accounting |
| `quote_bulk_price` | P5 | `pricing` | Accounting, Inventory |
| `get_cash_position` | P5 | `cash_accounts`, `payment_requests`, `payments`, `desk` | Boss, Accounting, Facilities |
| `list_payment_requests` | P5 | `payment_requests` | Boss, Accounting |
| `update_ticket` | P5 | `tickets`, `ticket_updates` | Boss |
| `save_draft` | P5 | `drafts` | Customer Service, Facilities |
| `request_payment` | P5 | `payment_requests` (validates against `invoices`, `leases`, `vendors`, `inventory`, `pricing`) | Accounting |
| `approve_and_pay` | P5 | `payment_requests`, `payments`, `cash_accounts`, `invoices`, `leases`, `vendors`, `ticket_updates` | **Human only** (operator role) |
| `reject_payment_request` | P5 | `payment_requests`, `ticket_updates` | **Human only** (operator role) |

`payment_requests`, `drafts` and `ticket_updates` are board tables the server creates in the working copy. `mcp_server/test_server.py` checks the rules offline on a temp copy of the original database:
- amounts come from the database ($840, $2,400, $264),
- a duplicate request is reused,
- requesting pays nothing,
- a purchase order is refused while #501 is open,
- an agent name can't approve,
- paying #501 and the rent leaves $160, marks #501 paid and moves the rent due date to 2026-10-02,
- the $264 purchase order is then refused instead of going negative.

### Test run (live, gpt-6-luna)
| Ticket | Team | Outcome on the board |
|---|---|---|
| 101 | Boss → Inventory, Accounting, Customer Service | Payment request #1 ($840, invoice #501, 3 days overdue) is pending. Draft #1 to Tauhid gives the honest timeline (5 days after the invoice is paid). Status `waiting_on_approval`. |
| 102 | Boss → Facilities, Accounting | The lease confirms the email: $2,400 due 2026-09-02, 2 days out. Payment request #2 is pending. Boss flagged that #1 + #2 leave $160. Status `waiting_on_approval`. |
| 103 | Boss → Inventory, Accounting, Customer Service | 8 on hand, 12 short. Restocking costs $264, but only $160 would be left after #1 and #2, so **no purchase order was requested**. Boss offered the 8 on hand at a discount within policy (52.6% margin). Draft #2 asks the club whether they want the partial order. Status `in_progress`. |

Each ticket used 11–15 model requests and roughly 37–64k tokens in total. No payment was made (`payments` stayed empty), because only a human can pay. The first live attempt failed on the Chat Completions API and is still in the audit trail as a `run_error`. One rerun of 103 also hit the old 4,000-token output cap, which was then raised and paired with low reasoning effort. After testing, the working database was reset to the original.

### Safety: guardrails a real business would want
Built into this system:
1. **People approve money.** Agents can only *request* payments. The pay tool isn't even registered for the agents' MCP connection (`CAMPUS_CUSTOMS_MCP_ROLE=agent`). It exists only for the human operator and rejects agent names as approvers.
2. **Money rules are enforced in code, not just in prompts.**
   - Amounts are read from the database, never taken from the model.
   - Payment is all-or-nothing in one database transaction.
   - The pay tool refuses rather than letting a balance go negative.
   - A vendor with an open invoice can't be paid for a new purchase order.
   - Duplicate requests are reused rather than created again.
3. **Least privilege.** Each agent sees only its own MCP tools, and only three tools write anything (ticket notes, drafts, payment requests). Read tools open the database read-only.
4. **Identity and scope are stamped by the harness.** The `agent` / `author` / `requested_by` fields, and the `ticket_id` on every write, are overwritten from the run context. A model can't act under another name or write to a different ticket.
5. **Nothing leaves the building.** Messages are drafts on the board, and there is no email or phone tool at all.
6. **Prompt-injection stance.** Ticket notes are marked as data, never instructions, both in every prompt and in the `get_ticket` field description.
7. **Secrets stay put.** The MCP subprocess gets a minimal environment with no API keys. Keys load from `.env` and are never logged.
8. **Full audit trail.** Every step, tool argument and tool result is appended with timestamps and a run tree. The working database can be reset from the untouched original.
9. **Customer privacy.** Prompts limit each draft to the requester's own name and order. Internal facts (cash, unpaid invoices, margins, the landlord) are never put in customer messages.

A real deployment would add:
- real user login and roles for approvers,
- two-person approval above a dollar threshold, and daily spending caps,
- personal data redaction in logs, with retention limits,
- encryption at rest,
- rate limits,
- tamper-evident (hash-chained) audit logs,
- and a human review step before any draft is actually sent.

### Limits that keep token use in check
| Limit | Value | Where |
|---|---|---|
| Model requests per ticket (whole delegation tree, shared budget) | 36 | `TICKET_LIMITS.request_limit` |
| Tool calls per ticket | 60 | `TICKET_LIMITS.tool_calls_limit` |
| Total tokens per ticket | 400,000 | `TICKET_LIMITS.total_tokens_limit` |
| Output tokens per model call (reasoning + answer) | 8,000, with `reasoning_effort="low"` | `MODEL_SETTINGS` |
| Delegation depth / delegations per ticket | 2 / 8 | `MAX_DELEGATION_DEPTH`, `MAX_DELEGATIONS_PER_TICKET` |
| Tool-error retries shown to the model | 2 | `TOOL_RETRIES` |
| Per-call timeouts | 90 s model, 30 s MCP | `REQUEST_TIMEOUT`, `MCP_TIMEOUT` |
| Size of tool output in the audit log | 2,000 characters | `audit.MAX_FIELD_CHARS` |

Other things that keep token use down:
- Every ticket starts with a fresh conversation, with no history carried over from earlier tickets.
- Tools return compact typed JSON.
- Prompts tell agents to call each tool once and to batch questions into one delegation.
- Each delegated agent gets a short self-contained task instead of the parent's whole transcript.

---

## Problem 6 — Plan for the Three Tickets

`output/desk_tickets.html` is a self-contained page with no server or build step: double-click it to open it. It has tabs for **101, 102, 103, Cash and Reflection**. Each ticket tab has a filled-in **Expected** section, written before the agents run, and an empty **Actual** section to fill in after the full run. Cash and Reflection say "coming in a later problem".

The plan assumes the tickets run in order 101 → 102 → 103 on a freshly reset database, because cash decisions carry from one ticket to the next.

| Ticket | Boss calls first (why) | Expected delegations | Not called |
|---|---|---|---|
| 101 tee S × 1 | **Inventory**: first find out whether it's on the shelf; the vendor block decides whether money is involved | Inventory → Accounting (request $840 for #501) → Customer Service (draft) | Facilities |
| 102 rent | **Facilities**: check the landlord's email against lease #1 before anyone pays | Facilities → Accounting (request $2,400; $160 left after both requests) | Inventory, Customer Service |
| 103 20 hoodies M | **Inventory**: price only what we can deliver (8 on hand, 12 short, vendor blocked) | Inventory → Accounting (quotes at 15% and 20%; the $264 reprint doesn't fit in $160, so no purchase order) → Customer Service (offer draft) | Facilities |

So the plan is 3 + 2 + 3 = 8 delegations, out of the 12 it would take for Boss to call every specialist on every ticket. Each tab also lists the MCP tools I expect each agent to call, with the arguments and the result I expect. It also lists the tools I *don't* expect, such as `request_payment` on 103 and `approve_and_pay` anywhere.

---

## Problem 7 — Backend Routes (`backend/main.py`)

Start it from `HW 5/backend` with `..\.venv\Scripts\activate`, then `uvicorn main:app --reload --port 8000`. It runs at http://localhost:8000, with interactive docs at `/docs`. CORS allows the Vite dashboard on `localhost:5173`. The backend reads shop facts **through the MCP server**, never straight from SQLite, over two connections:
- the agents' connection (role `agent`, where no tool can move money),
- an `operator` connection used only by the human approve and reject routes. That makes approve the **only** path that changes cash.

| Method | URL | What it does |
|---|---|---|
| GET | `/api/tickets` | All tickets with their board status, an `open`/`resolved` flag, and whether an agent run is working on each right now. |
| GET | `/api/tickets/{id}` | One ticket in full: linked invoice and lease, status history, drafts, and payment requests. |
| POST | `/api/tickets/{id}/run` | Runs the agent team (Boss first) on that ticket. Returns a job id right away, or with `?wait=true` returns the Boss's `TicketOutcome`. Only one run at a time (409 if busy). |
| GET | `/api/runs` · `/api/runs/{job_id}` | Status of agent runs started from the API (queued, running, done or failed), with their outcome or error. |
| GET | `/api/events?since=&ticket_id=&agent=&limit=` | Recent agent events from `output/audit_trail.json`: who acted, what they said, which tools and delegations they used, and short tool results. Poll with `since=<next_since>` to get only new events. |
| GET | `/api/payment-requests?status=` | Payments and purchase orders the agents prepared. Defaults to the ones `pending_approval`. |
| POST | `/api/payment-requests/{id}/approve` | **Human clicks Approve**: body `{approved_by}`. Pays through MCP `approve_and_pay` and updates payments, cash_accounts and invoices or leases. Returns 409 with the reason if refused (cash short, vendor blocked, already paid, agent name). |
| POST | `/api/payment-requests/{id}/reject` | Human rejects a request: body `{rejected_by, reason}`. No money moves. |
| GET | `/api/cash` | Current **checking balance** from `cash_accounts`, plus the pending total, cash after pending, and payments made. |
| POST | `/api/reset` | Resets `data/campus_customs_new.db` to the original values for a fresh run. The audit trail is not touched. Refused while a run is in progress. |
| GET | `/api/health` | Server up, model name, whether the agents are ready. |

**Status codes:** unknown ids return 404. A refusal by a shop rule returns 409 with the tool's own message.

**Tested live:**
- reset → run 101 → 1 pending request of $840 and a draft;
- approving as "accounting" → 409 "must be the human approver";
- approving as a person → paid, checking $3,400 → $2,560, invoice #501 `paid`, a `human:` note added to the ticket history;
- approving again → 409 "not pending";
- unknown request → 404;
- reset → all three tickets `open`, checking back to $3,400, no payments.

**Fix found while testing.** Near the end of ticket 101, Boss repeatedly spent its whole 8,000-token reply budget thinking and never returned its `TicketOutcome`. Its board writes were already done. `team.run_agent` now catches that one failure and resumes **once** from the run's own message history. The retry uses a *tool-less twin* of the same agent with reasoning off and a "return your final output now" prompt, so it can't repeat any work. It's logged as `run_retry`. The first version of the retry kept the agent's tools, and Boss looped on `get_ticket` until the 400k-token ticket budget stopped it. That run is still in the audit trail, which shows the per-ticket limit doing its job.

**Two more fixes:**
- Writes to `audit_trail.json` now retry for a moment when OneDrive briefly locks the file.
- The app's shutdown closes its MCP connections with a timeout, so a `--reload` restart can't hang.

---

## Problem 8 — Agent Dashboard (`frontend/`)

React 19 + Vite + TypeScript, with no UI library. Run `npm install` once, then `npm run dev` from `HW 5/frontend`; it opens http://localhost:5173. The browser calls the backend **directly at `http://localhost:8000`** (override with `VITE_API_URL`). `main.py`'s CORS middleware allows `http://localhost:5173` and `http://127.0.0.1:5173`. The design rationale is in `output/design.md`.

| Requirement | Where on the desk | Backend route |
|---|---|---|
| List all three tickets | Ticket rail (paper slips with status pills) | `GET /api/tickets` |
| Pick a ticket and start the team | Click a slip (or press 1–3), then **Hand it to the team** (or press R) | `POST /api/tickets/{id}/run` |
| Show each agent and what it's saying and doing live | Round table: seats light up with a human verb and the live tool arguments, speech bubbles, and hand-off wires. Plus the transcript, polled every 1.2 s. | `GET /api/events?since=`, `GET /api/runs/{job}` |
| Mark the ticket resolved when the run finishes | RESOLVED stamp animates onto the slip, plus a toast | `GET /api/tickets` (`state`) |
| Short summary of what each agent did | Debrief: one card per agent, in its own voice; who wasn't called | events `run_end.output`, `GET /api/tickets/{id}` (drafts) |
| Human approves a payment or purchase | Cash drawer: **checks to sign** (needs a signature; Sign & pay or Void) | `GET /api/payment-requests`, `POST …/approve`, `POST …/reject` |
| Checking balance that drops after approval | Rolling-counter balance, −$ tag, register tape | `GET /api/cash` |
| Extra | Run replay scrubber, runway bar, desk calendar for the shop date, two-click "Start a fresh day" | `POST /api/reset` |

**Backend changes made for the desk:**
- **`GET /api/tickets`** now returns `state` (`open`, `running` or `resolved`), along with `pending_approvals`, Boss's latest decision, the draft count, and the ticket's item and notes. `resolved` means the team finished its run and Boss recorded the final call (or the board status is `resolved`). The board status itself is kept separately, so pending money is never hidden.
- **`GET /api/payment-requests`** adds the `payee`, looked up through MCP (vendor or landlord), for the check.
- **`/approve`:** when the last pending check on a ticket is paid, the ticket moves on automatically. Rent becomes `resolved`; an invoice or purchase order becomes `waiting_on_vendor`. The change is recorded as a `human:<name>` update in the ticket history.
- **`GET /api/events`** now includes each `run_end` output, so the debrief can show the agents' own reports.

**Verified in the browser:**
- Reset, then ran ticket 101 from the desk. The seats and wires updated live (Boss → Inventory → Accounting → Customer Service; Facilities stayed greyed out).
- The slip got its RESOLVED stamp and "1 check to sign".
- Signed the $840 check as a human. The counter rolled from $3,400.00 to $2,560.00, the register tape printed `INV 501 −$840.00 ok Juan Pablo`, and the ticket moved to `waiting on vendor`.
- "Start a fresh day" restored $3,400, three open tickets and an empty tape.
- `tsc -b` and `vite build` pass.

---

## Problem 9 — Resolving the Tickets (full run)

**Procedure:**
1. Reset `data/campus_customs_new.db` from the original (identical SHA-1 `f447ca6a…`). The starting checking balance was **$3,400.00**, with no payments.
2. Ran tickets **101 → 102 → 103** through `POST /api/tickets/{id}/run?wait=true`, using the same Team the dashboard uses.
3. The two checks the agents prepared were approved through `POST /api/payment-requests/{id}/approve` with `approved_by = "Juan Pablo"`, on the owner's explicit instruction for this run.
4. Took screenshots of each resolved ticket's desk at 1440×900 with headless Edge, using the new `#ticket=<id>` deep link.

The run added audit entries 487–588 (102 steps) to `output/audit_trail.json`. Nothing was overwritten.

| Ticket | Agents (in order) | Tools | Requests / tokens | Result |
|---|---|---|---|---|
| 101 | Boss → Inventory → Accounting → Customer Service | get_ticket, check_stock, get_vendor_status, get_invoice, get_cash_position, list_payment_requests, request_payment, save_draft, update_ticket, list_tickets | 18 / ~92k (one `run_retry`) | Request #1 for $840 paid, invoice #501 `paid`, ticket `waiting_on_vendor`, draft #1 |
| 102 | Boss → Facilities → Accounting | get_ticket, get_rent_status, get_cash_position, request_payment, update_ticket | 12 / ~42k | Request #2 for $2,400 paid, lease next_due → 2026-10-02, ticket `resolved` |
| 103 | Boss → Inventory → Accounting (→ Inventory) → Customer Service | get_ticket, check_stock, get_vendor_status, quote_bulk_price ×3, get_cash_position, get_invoice, save_draft, update_ticket | 15 / ~52k | 15% on 8 hoodies ($49.30), no purchase order ($264 > $160), draft #2, ticket `in_progress` |

**Cash:** $3,400.00 − $840.00 − $2,400.00 − $0.00 = **$160.00**. This equals `cash_accounts.balance` for `checking`. `SUM(payments.amount)` = $3,240.00, nothing is pending, and the balance never went negative.

**Plan vs. actual:** the first calls and the agents left out matched on all three tickets: Facilities on 101 and 103, Inventory and Customer Service on 102. Three differences show up in `desk_tickets.html`:
- On 101, Boss made an extra `list_tickets` call and hit the token limit at the end, which the retry fixed.
- On 102, Accounting re-read the rent status.
- On 103, Accounting delegated to Inventory again, an unplanned 4th hand-off.

A tighter Accounting prompt ("trust facts passed in the task; don't re-delegate for them") would remove the last one.

**Deliverables:**
- `output/desk_tickets.html`: Actual sections and the Cash tab.
- `output/resolved_tickets.json`: per ticket, the id, final status, outcome, each agent's contribution, and human approvals.
- `output/resolved_board.html` and `output/screenshots/`: the board for each resolved ticket, plus 101 before signing.
- `output/audit_trail.json`: appended.

---
