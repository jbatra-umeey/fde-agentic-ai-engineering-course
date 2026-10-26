"""LLM-backed supervisor and specialists; evidence-only outputs cannot deploy code."""

import asyncio
from typing import Literal

from jev_core.models import DomainError, StrictModel
from jev_core.prompt_registry import load_prompt
from pydantic import Field, model_validator

from .patterns import analyze

Role = Literal["research", "coding", "analysis", "security"]


class Task(StrictModel):
    role: Role
    task: str = Field(min_length=5, max_length=600)


class Plan(StrictModel):
    tasks: list[Task] = Field(min_length=2, max_length=4)

    @model_validator(mode="after")
    def required_reviewers(self):
        roles = [t.role for t in self.tasks]
        if len(set(roles)) != len(roles) or not {"analysis", "security"} <= set(roles):
            raise ValueError("Unique roles including analysis and security required")
        return self


class SpecialistReport(StrictModel):
    finding: str = Field(min_length=5, max_length=1800)
    risk: Literal["low", "medium", "high", "unknown"]
    evidence_ids: list[str] = Field(max_length=10)
    missing_evidence: list[str] = Field(max_length=10)
    suggested_code: str | None = Field(default=None, max_length=3000)


async def llm_release_review(router, dataset, documents):
    # Explicitly synthetic evidence, shared across specialists without credentials or tenant IDs.
    evidence = {
        "metrics": analyze(dataset),
        "documents": documents[:3],
        "security_scan": None,
        "synthetic": True,
    }
    plan = await router.generate(
        load_prompt("supervisor"),
        {
            "goal": "Assess release readiness; no deployment is authorized",
            "allowed_roles": ["research", "coding", "analysis", "security"],
            "evidence": evidence,
        },
        Plan,
        "supervisor",
    )
    known_ids = {doc["id"] for doc in evidence["documents"]}

    async def worker(task):
        report = await router.generate(
            load_prompt("specialist"),
            {
                "role": task.role,
                "task": task.task,
                "evidence": evidence,
            },
            SpecialistReport,
            f"specialist:{task.role}",
        )
        if not set(report.evidence_ids) <= known_ids:
            raise DomainError("specialist_unsupported_citations", 422)
        return report.model_dump()

    async with asyncio.TaskGroup() as group:
        tasks = {task.role: group.create_task(worker(task)) for task in plan.tasks}
    reports = {role: task.result() for role, task in tasks.items()}
    blocked = evidence["metrics"]["regression"] or any(
        r["risk"] in {"high", "unknown"} or r["missing_evidence"] for r in reports.values()
    )
    # Absence of a real scan always holds this synthetic release, regardless of LLM optimism.
    blocked = blocked or evidence["security_scan"] is None
    return {
        "specialists": {"planning": plan.model_dump(), **reports},
        "recommendation": "HOLD" if blocked else "PROCEED_TO_HUMAN_REVIEW",
        "synthetic": True,
        "mode": "llm",
        "code_executed": False,
        "policy_reasons": ["No real security scan supplied"],
    }
