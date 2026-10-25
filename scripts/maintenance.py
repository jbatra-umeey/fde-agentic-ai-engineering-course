"""Operator-owned backup/cleanup; these operations are not agent tools."""

import argparse
import sqlite3
from pathlib import Path

from jev_core.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["backup", "purge"])
    parser.add_argument("--db", required=True)
    parser.add_argument("--destination")
    args = parser.parse_args()
    if not Path(args.db).is_file():
        parser.error("Source database does not exist")
    if args.operation == "purge":
        Store(args.db).purge_expired()
        print("Expired memory and old rate counters purged.")
        return
    if not args.destination or Path(args.destination).exists():
        parser.error("Choose a new --destination path")
    Path(args.destination).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.db) as source, sqlite3.connect(args.destination) as destination:
        source.backup(destination)
        assert destination.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    Path(args.destination).chmod(0o600)
    print("Backup complete; integrity check passed.")


if __name__ == "__main__":
    main()
