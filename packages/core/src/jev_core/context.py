"""Deterministic retrieval and explicit trusted/untrusted context boundaries."""

import re

from .models import canonical
from .prompt_registry import load_prompt

SYSTEM_RULES = load_prompt("planner").text


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def retrieve(store, tenant, query, limit=3):
    tokens = words(query)
    ranked = sorted(store.docs(tenant), key=lambda d: (-len(tokens & words(d["content"])), d["id"]))
    return [d for d in ranked if tokens & words(d["content"])][:limit]


def build_context(store, principal, state, tools, budget_bytes=16000):
    """A hard serialized-byte budget, not a claim of model-token accuracy.

    Preserve instructions/tool schemas and newest observations. Drop old memory
    first, then lowest-ranked docs, then old observations. Never truncate JSON.
    """
    request = state["request"]
    context = {
        "system": SYSTEM_RULES,
        "scenario": request["scenario"],
        "goal": request["goal"],
        "tools": tools,
        "evidence": retrieve(store, principal.tenant, request["goal"]),
        "memory": store.memory_get(principal, request["session"]),
        "observations": state["observations"][-6:],
    }
    while len(canonical(context).encode()) > budget_bytes:
        if context["memory"]:
            context["memory"].pop(0)
        elif context["evidence"]:
            context["evidence"].pop()
        elif len(context["observations"]) > 1:
            context["observations"].pop(0)
        else:
            raise ValueError("Required context exceeds budget")
    return context
