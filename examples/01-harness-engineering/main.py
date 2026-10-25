"""Runnable companion to module 1: Harness Engineering."""

import asyncio
import json

from jev_cli.lessons import run_lesson

if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_lesson(1)), indent=2))
