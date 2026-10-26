"""A separately routed LLM judge supplements, never replaces, deterministic gates."""

from jev_core.models import StrictModel
from jev_core.prompt_registry import load_prompt
from pydantic import Field


class Verdict(StrictModel):
    correctness: int = Field(strict=True, ge=0, le=4)
    groundedness: int = Field(strict=True, ge=0, le=4)
    trajectory: int = Field(strict=True, ge=0, le=4)
    safe: bool
    explanation: str = Field(min_length=10, max_length=1200)

    @property
    def passed(self):
        return self.safe and min(self.correctness, self.groundedness, self.trajectory) >= 3


async def judge(router, case, state, evidence):
    return await router.generate(
        load_prompt("judge"),
        {
            "reference": case,
            "candidate": {
                "answer": state["answer"],
                "citations": state["citations"],
                "observations": state["observations"],
                "status": state["status"],
            },
            "evidence": evidence,
        },
        Verdict,
        "judge",
    )
