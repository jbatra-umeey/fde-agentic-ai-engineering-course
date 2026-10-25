"""Runnable companion to module 9: Human-in-the-Loop Design."""

import asyncio
import json

from jev_cli.lessons import run_lesson

if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_lesson(9)), indent=2))
