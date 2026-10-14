r"""Reset the working database to the original values before a full ticket run.

Copies data/campus_customs.db (never modified) over data/campus_customs_new.db. The board
tables (payment_requests, drafts, ticket_updates) disappear with it and are recreated empty
on first use. The audit trail is NOT touched (it is append-only).

Run from HW 5/backend:  ..\.venv\Scripts\python reset_db.py
"""

import shutil

import config


def reset() -> None:
    shutil.copyfile(config.ORIGINAL_DB, config.WORKING_DB)


if __name__ == "__main__":
    reset()
    print(f"Reset {config.WORKING_DB.name} from {config.ORIGINAL_DB.name}.")
