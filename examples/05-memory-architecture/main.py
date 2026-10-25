"""Runnable companion to module 5: Memory Architecture."""

import asyncio
import json

from jev_cli.lessons import run_lesson

if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_lesson(5)), indent=2))
