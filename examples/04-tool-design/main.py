"""Runnable companion to module 4: Tool Design."""

import asyncio
import json

from jev_cli.lessons import run_lesson

if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_lesson(4)), indent=2))
