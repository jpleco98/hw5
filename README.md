# Campus Customs Multi-Agent Operations (HW5)

An agent team runs the Campus Customs shop's ticket board. **Boss** reads each ticket and delegates to **Inventory**, **Accounting**, **Facilities** and **Customer Service** (any agent can delegate to any other). The agents work only through an **MCP server** over the shop database. A **FastAPI** backend runs the team, and a **React** desk lets a human watch the agents and **sign the payments** they prepare.

```
React desk (frontend/, :5173) ──► FastAPI (backend/main.py, :8000) ──► agent team (backend/team.py, gpt-6-luna via Portkey)
                                         │                                   │
                                         └──── MCP server (mcp_server/server.py, FastMCP) ◄┘
                                                         │
                                       data/campus_customs_new.db   (working copy: everything reads and writes here)
                                       data/campus_customs.db       (original: never written; used only to reset)
```

## Repository layout
```
hw5/
├── AI_prompts.md            prompts typed to the vibe coder, one section per problem
├── requirements.txt         Python deps (fastmcp, pydantic-ai-slim[openai,mcp], python-dotenv, fastapi, uvicorn)
├── .env.example             copy to .env and add your PORTKEY_API_KEY (the real .env is git-ignored)
├── .mcp.json                lets Claude Code / an MCP client launch the server
├── data/
│   ├── campus_customs.db        original shop database (reset source)
│   └── campus_customs_new.db    working copy, as left by the final graded run (checking = $160)
├── mcp_server/              server.py (14 tools), README.md, test_server.py (offline rule tests)
├── backend/                 main.py (FastAPI), team.py (agent loop), models.py, config.py, audit.py,
│                            agents/ (one file per role), prompts/ (one .md per agent), reset_db.py, run_tickets.py
├── frontend/                React + Vite + TypeScript desk
└── output/                  harness.md, mcp_smoke.json, desk_tickets.html, design.md, resolved_tickets.json,
                             resolved_board.html (+ screenshots/), audit_trail.json, github_url.txt
```

## 0. One-time setup
Requirements: Python 3.11+ (built on 3.13) and Node 20+ (built on 24).

```bash
# from the repo root
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # Windows: copy .env.example .env
# then edit .env and set PORTKEY_API_KEY=...  (every agent uses gpt-6-luna through Portkey)

cd frontend && npm install && cd ..
```

## 1. Copy the original database to the working copy (clean start)
The app only reads and writes `data/campus_customs_new.db`. When you want a clean run, copy the untouched original over it:

```bash
# macOS/Linux
cp data/campus_customs.db data/campus_customs_new.db
# Windows (PowerShell)
Copy-Item data\campus_customs.db data\campus_customs_new.db -Force
# or, from any OS:
python backend/reset_db.py
```
The repo ships the working copy **after** the graded run (two payments, checking $160), so do this first if you want to watch the tickets from the start.

## 2. Start the MCP server
```bash
python mcp_server/server.py          # stdio transport, "agent" role (no tool can move money)
```
- **You don't need a separate terminal for the app.** The FastAPI backend launches its own copies of this server: one with the *agent* role for the team, and one with the *operator* role, used only by the human approve and reject routes.
- **Run it by hand** to connect an MCP client. `.mcp.json` registers it for Claude Code; start Claude from an activated venv so `python` resolves.
- **Offline rule tests:** `python mcp_server/test_server.py` runs on a temp copy of the original database and needs no API key.

## 3. Start the FastAPI backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```
- The backend runs at http://localhost:8000, with interactive docs at http://localhost:8000/docs.
- CORS allows the desk at http://localhost:5173.
- Main routes:
  - `GET /api/tickets`
  - `POST /api/tickets/{id}/run`
  - `GET /api/events`
  - `GET /api/payment-requests`
  - `POST /api/payment-requests/{id}/approve`
  - `GET /api/cash`
  - `POST /api/reset`

## 4. Start the React board
```bash
cd frontend
npm run dev                          # opens http://localhost:5173
```
- **Pick a ticket and run it:** choose a ticket on the left rail and click **Hand it to the team**. Watch the agents on the corkboard, where hand-offs show as red string.
- **Sign the checks:** in the cash drawer, type your name on a check's signature line and click **Sign & pay**. The balance drops.

## 5. Full three-ticket run (reset first!)
Always reset the working database before a full run, so cash starts at $3,400.00:
- **On the desk:** click **Start a fresh day** (click twice to confirm), then run tickets 101, 102 and 103. Sign the checks the agents prepare.
- **From the terminal:** `cd backend && python run_tickets.py --all --reset`. This runs all three tickets and leaves the checks pending for a human. Approve them on the desk or with `POST /api/payment-requests/{id}/approve`.

**Expected result:**

| Ticket | What the team does | Cash change |
|---|---|---|
| 101 | Requests $840 for overdue invoice #501, which blocks the vendor | −$840 |
| 102 | Requests the $2,400 rent | −$2,400 |
| 103 | 15% off the 8 hoodies in stock; no purchase order, because $264 > the $160 left | $0 |

$3,400 − $840 − $2,400 = **$160.00** in `cash_accounts`.

## Shop rules the system enforces
- **The shop date** is `desk.date_today` (2026-08-31). Overdue is measured against it.
- **Vendor block:** a vendor won't ship while it has an open unpaid invoice. Lead times come from `vendors.lead_days`.
- **Human approval:** every payment needs a person. Agents can only *request* payments; the pay tool exists only on the operator connection the approve route uses.
- **No negative balances:** the pay tool refuses rather than go negative. Cash only goes out, because no revenue is modeled.
- **Tables kept in sync:** paying updates `payments`, `cash_accounts`, and `invoices` or `leases` in one transaction.
- **Nothing is sent:** customer, vendor and landlord messages stay as drafts on the board.
- **Audit trail:** every agent-loop step is appended to `output/audit_trail.json`.

The full design write-up is in `output/harness.md`, and the dashboard design is in `output/design.md`.
