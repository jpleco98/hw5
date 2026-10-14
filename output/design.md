# Campus Customs Back Office: Dashboard Design

**What it is:** a React + Vite + TypeScript desk in `frontend/` that calls the FastAPI routes at `http://localhost:8000`. Start it with `npm run dev` from `frontend/`; it opens http://localhost:5173.

**The idea in one line:** this is the **back office of a small shop**, not an analytics dashboard. The person using it is the owner, and their real jobs are reading tickets, watching the team, and signing checks. So the page is built from objects that already belong on a shop desk:
- a ticket rail,
- a corkboard the staff gather around, with the ticket pinned to it,
- a cash drawer,
- a checkbook,
- a register tape,
- and a desk calendar.

Every piece is a real control, not decoration.

---

## Layout: three zones, read left to right like the work itself

```
┌──────────────────────────── navy top bar: brand · desk calendar (shop date) · team presence · Start a fresh day ┐
│  THE RAIL            │  THE TABLE                                               │  THE CASH DRAWER        │
│  paper tickets       │  brief + "Hand it to the team"                           │  rolling-counter balance│
│  clipped to a steel  │  five agents around a corkboard, red-yarn hand-offs,     │  runway bar             │
│  bar; stamps show    │  wires show who handed work to whom                      │  checks to sign         │
│  state               │  replay scrubber                                         │  register tape          │
│                      │  At the table (transcript)  │  Debrief (one card per agent) │                         │
└──────────────────────┴──────────────────────────────────────────────────────────┴─────────────────────────┘
```

1. **Inbox on the left.** Tickets hang from a steel rail like order slips in a kitchen pass. The torn bottom edge, slight tilt and clip make them read instantly as "papers waiting for someone". The selected ticket straightens and drops a little, like pulling a slip off the rail. Keys **1–3** pick a ticket.
2. **Work in the middle.** The selected ticket is **pinned to a corkboard** in a wooden frame (red push pin, a spare pin, a sticky note), with the five agents gathered around it. This was chosen from four sketched options (shop floor plan, corkboard, print-shop cutting mat, crest watermark) after a round wooden table and a leather blotter didn't feel right. The corkboard won because it gives the hand-offs a physical meaning: they become **red string between pins**, like an investigation board. One big button, **"Hand it to the team"** (or press **R**), gives the ticket to Boss. Below the table: the live transcript on the left, and the debrief on the right.
3. **Money on the right.** The cash drawer is the only dark panel. It's where the irreversible actions live, so it should feel heavier and more serious than the paper around it.

Why this order: a person's eye moves left to right, and so does the work: *what's waiting → who's working on it → what it costs me*. The thing you might have to sign is always in the same place, always visible, never hidden in a modal.

---

## How the agents read differently

Telling agents apart by color alone fails for color-blind users and gets lost in a long transcript. So each agent has three separate cues: a **shape**, a **color**, and a **written voice**. The voices all come from one variable font (Recursive) whose *mono* and *casual* settings change per agent, plus a serif for letters. The page stays coherent, but each agent "writes" differently.

| Agent | Badge shape | Color | Voice in the transcript and debrief |
|---|---|---|---|
| **Boss** | rounded square with a gold ★ | Yale navy | **Memo**: bold, upright sans, like a decision written on a memo pad |
| **Inventory** | price-tag shape | shelf green | **Stock tag**: monospaced, like a label printer (`CC-TEE-WHITE · S · 1`) |
| **Accounting** | coin (circle) | oxblood | **Ledger paper**: monospaced tabular numbers on green-ruled paper with a red margin line |
| **Facilities** | little house | blueprint blue | **Blueprint**: small grid background, drafting-style lettering |
| **Customer Service** | speech bubble | terracotta | **Letter**: italic serif, warm brown ink. Their drafts appear as an actual letter on cream paper, marked *not sent* |

**Around the table:**
- Each seat shows a human verb for what the agent is doing right now, never a raw tool name. `check_stock` reads as "checking the shelf", `get_cash_position` as "counting the drawer", and `request_payment` as "writing you a check to sign". The real arguments sit next to the verb in small mono type, for anyone who wants detail.
- The agent working right now has a pulsing ring. Agents who haven't been called stay greyed out and show their job description. So you can see at a glance that **Facilities wasn't needed on ticket 101**, which is the "don't send everyone" principle made visible.
- **Red-string hand-offs:** when one agent delegates to another, a strand of red yarn is pulled across the corkboard from the delegator to the delegate (it draws itself in, then gently tugs while the teammate works). When the delegate reports back, the string relaxes to a thinner, settled line, so the finished board is the actual org chart of that run, strung like an investigation board.

---

## How resolved tickets show up

- **While running:** the slip on the rail says *team at work* with a pulsing dot, the ticket on the table gently "breathes", and the run button shows a spinner with *"Inventory has it"* (whoever is active).
- **When the run finishes:** a red **RESOLVED** rubber stamp slams onto the slip. It's a CSS animation: it scales in from 2.4×, overshoots, and settles at a slight angle with a *multiply* blend so it looks inked onto the paper. A toast says *"Ticket 101 resolved by the team: 1 check waiting for your signature."*
- **"Resolved" vs. the money:** *resolved* means the team finished its run and Boss recorded the final call. The slip also keeps the real board status as a small pill (*waiting on you*, *waiting on vendor*, *resolved*) and a navy **"1 check to sign"** pill. So "the agents are done" and "money still needs you" are never confused.
- **After you sign:** the backend moves the ticket forward by itself. Rent becomes *resolved*; an invoice or purchase order becomes *waiting on vendor*, because the product still has to arrive.
- **Debrief:** one card per agent who took part, in that agent's voice:
  - Boss's card is the memo: the decision, the why, **For you** (next steps), and **Watch out** (risks).
  - Specialists show their summary, their key facts as a little ledger (each fact still carries the tool it came from, shown on hover), their actions, and a tool belt of what they used and who they handed off to.
  - A line at the top says who was *not called this time*.

---

## How cash shows up

- **Rolling counter.** The checking balance is a mechanical counter: each digit is a drum that rolls when the number changes. After you sign a check, you *watch* $3,400.00 roll down to $2,560.00, with a gold **−$840.00** tag. A balance that visibly moves makes spending money feel like spending money.
- **Runway bar.** It shows how much of the balance the checks on your desk would use, one segment per check (invoice, rent and purchase order in different colors), plus *"$160.00 left if you sign all"*. If the checks add up to more than the cash, the number turns red and a warning says the bank will refuse the last one. That matches the pay tool's real refusal rule.
- **Checks to sign.** The agents' payment requests appear as **actual checks**:
  - *Pay to the order of* Bulldog Print Co, the amount in a box, the amount **written out in words** ("Eight hundred forty and 00/100 dollars"), the memo (Accounting's reason, with the overdue days and the cash left), *Prepared by accounting*, and a signature line.
  - Spelling the amount in words is a real-world safeguard: it makes you read the number twice before you sign.
  - You sign by typing your name **right on the check's signature line** (it also fills *Signing as* and is remembered for the next checks), and it appears in handwriting. Until you sign, **Sign & pay** stays disabled and a note under the check says why. During an agent run it explains that you can sign as soon as the run ends.
  - **Void** rejects the check, and no money moves.
  - If the backend refuses (cash short, vendor blocked, already paid), the refusal shows right on the check in red.
- **Register tape.** Every payment made prints on a thermal-receipt strip with a torn edge: date, `INV 501` or `RENT L1`, the amount, and *ok Juan Pablo* (who approved it). It's the audit trail in a form anyone in a shop recognizes.
- **Desk calendar.** The top bar has a desk calendar showing **Mon 31 Aug 2026**: the *shop's* date (`desk.date_today`), not today's real date. Every "overdue" on the page is measured from it, and having it on the desk makes that obvious.

---

## Creative and functional extras

1. **Replay the run.** After a run, a scrubber lets you replay it step by step (▶ or drag). The table, wires, speech bubbles and debrief rebuild exactly as they were at that step, from the audit trail. It's like game film for your agents. It's useful for spotting where a decision came from, and it uses the same function that draws the live view.
2. **Archived runs.** After a reset, a ticket is open again on today's board, but you can still open *"the last archived run from the audit trail"*, because the trail is append-only.
3. **Start a fresh day.** Resetting the database is a two-click action: the button turns red and says *"Click again to wipe the board"*. You can't reset by accident, and there's no annoying modal.
4. **Live meter** under the table: hand-offs so far, how many of the 5 agents are at the table, and tokens used on this ticket. Cost is visible while it happens.
5. **Keyboard:** 1–3 pick a ticket, R runs it. Animations respect *reduced motion*.

---

## Why it should be pleasant to sit at

- **Warm, quiet materials.** Linen desk, paper, cork, a steel rail. There are no neon dark-mode charts. The only dark surface is the cash drawer, so your attention goes to money exactly when it should.
- **Glanceable from across the room.** Stamps, pills, the rolling counter and the pulsing ring are all readable without reading text.
- **Trust through honesty.** Nothing claims more than the backend says. Drafts are marked *not sent*. Checks say *needs a human signature*. Agents who weren't needed are shown as not needed. The page never moves money on its own: every dollar goes out through a check you signed.
- **Real objects make the rules intuitive.** You don't need to be told that agents can't pay. They hand you checks, and you sign them.

**Tech notes:**
- React 19, Vite, TypeScript, no UI library.
- Fonts are bundled locally via Fontsource (Recursive, Newsreader, Caveat, Special Elite), so the desk works offline.
- The page polls `/api/events?since=` every 1.2 s during a run (4 s when idle) and refreshes the board, cash and checks every 2.5–5 s.
- The backend's CORS allows `http://localhost:5173` and `http://127.0.0.1:5173`.
