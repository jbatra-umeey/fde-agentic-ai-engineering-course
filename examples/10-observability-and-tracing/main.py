"""Runnable companion to module 10: Observability & Tracing."""

import asyncio
import json

from jev_cli.lessons import run_lesson

if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_lesson(10)), indent=2))
