"""Run outside the source tree after installing the wheel; verifies bundled resources."""

import asyncio

from jev_cli.lessons import run_lesson
from jev_core.prompt_registry import load_prompt
from jev_evals.runner import evaluate, load_dataset


async def main():
    for name in ["planner", "supervisor", "specialist", "judge"]:
        assert len(load_prompt(name).sha256) == 64
    for number in range(1, 11):
        assert await run_lesson(number)
    report = await evaluate(cases=load_dataset() + load_dataset("injection.v1"))
    assert report["gate"]
    print("Installed wheel: four prompts, ten lessons and eight evaluation cases passed")


if __name__ == "__main__":
    asyncio.run(main())
