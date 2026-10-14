r"""Run the agent team on the ticket board from the terminal.

    ..\.venv\Scripts\python run_tickets.py 101          # one ticket
    ..\.venv\Scripts\python run_tickets.py --all --reset  # full run on a fresh database

Every agent-loop step is appended to output/audit_trail.json. Payments are only
*requested*; a human approves them later (dashboard / operator MCP tools).
"""

import argparse
import asyncio
import os
import sqlite3

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

import config  # noqa: E402
import reset_db  # noqa: E402
from team import Team  # noqa: E402


def open_ticket_ids() -> list[int]:
    with sqlite3.connect(f"file:{config.WORKING_DB.as_posix()}?mode=ro", uri=True) as conn:
        return [r[0] for r in conn.execute("SELECT id FROM tickets WHERE status = 'open' ORDER BY id")]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tickets", nargs="*", type=int, help="ticket ids (default: all open)")
    parser.add_argument("--all", action="store_true", help="run every open ticket")
    parser.add_argument("--reset", action="store_true", help="reset the working DB from the original first")
    args = parser.parse_args()

    if args.reset:
        reset_db.reset()
        print("Working database reset to the original values.")
    ids = args.tickets or open_ticket_ids()

    async with Team() as team:
        print(f"Session {team.session_id}: tickets {ids}")
        for tid in ids:
            print(f"\n=== Ticket {tid} ===")
            try:
                outcome = await team.run_ticket(tid)
            except Exception as exc:  # noqa: BLE001
                print(f"FAILED: {type(exc).__name__}: {exc}")
                continue
            print(outcome.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
