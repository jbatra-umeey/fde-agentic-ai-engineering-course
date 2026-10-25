"""Runnable companion to module 8: Evals for Agents."""

import asyncio
import json

from jev_cli.lessons import run_lesson

if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_lesson(8)), indent=2))
