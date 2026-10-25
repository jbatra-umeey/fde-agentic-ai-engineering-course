"""Runnable companion to module 6: Orchestration Patterns."""

import asyncio
import json

from jev_cli.lessons import run_lesson

if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_lesson(6)), indent=2))
