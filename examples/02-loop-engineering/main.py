"""Runnable companion to module 2: Loop Engineering."""

import asyncio
import json

from jev_cli.lessons import run_lesson

if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_lesson(2)), indent=2))
