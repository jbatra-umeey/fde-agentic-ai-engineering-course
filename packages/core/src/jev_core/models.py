"""Boundary schemas reject unknown fields; identity never comes from model output."""

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Scenario = Literal["knowledge", "incident", "mobile_performance", "refund", "release"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Principal(StrictModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant: str = Field(min_length=1, max_length=100)
    subject: str = Field(min_length=1, max_length=100)
    role: Literal["operator", "reviewer", "reader"]


class RunRequest(StrictModel):
    scenario: Scenario
    goal: str = Field(min_length=3, max_length=2000)
    session: str = Field(default="default", min_length=1, max_length=100, pattern=r"^[\w-]+$")
    remember: bool = False


class Decision(StrictModel):
    kind: Literal["tool", "final"]
    tool: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    answer: str | None = Field(default=None, max_length=4000)
    citations: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def consistent(self):
        if self.kind == "tool" and (not self.tool or self.answer or self.citations):
            raise ValueError("Tool decisions require a tool and no answer/citations")
        if self.kind == "final" and (not self.answer or self.tool or self.arguments):
            raise ValueError("Final decisions require an answer and no tool/arguments")
        return self


class Approval(StrictModel):
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    approve: bool


class DomainError(Exception):
    def __init__(self, code: str, status: int = 409):
        self.code, self.status = code, status
        super().__init__(code)


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()
