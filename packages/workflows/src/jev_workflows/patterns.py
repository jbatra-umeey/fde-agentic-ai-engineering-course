"""Sequential, parallel, and supervisor/router patterns without framework lock-in."""

import asyncio
import math
import subprocess
import sys

DATASETS = {
    "incident": {"baseline": [90, 100, 110, 120, 125], "current": [120, 145, 160, 190, 250]},
    "mobile_performance": {
        "baseline": [800, 850, 900, 1000, 1200],
        "current": [900, 1000, 1200, 1800, 2400],
    },
    "release": {"baseline": [100, 110, 120, 130, 140], "current": [95, 100, 110, 120, 130]},
}


def percentile(values, q):
    """Nearest-rank percentile; synthetic five-sample data is illustrative only."""
    if not values or not 0 < q <= 1:
        raise ValueError("Nonempty samples and percentile in (0,1] required")
    return sorted(values)[max(0, math.ceil(len(values) * q) - 1)]


def analyze(dataset):
    samples = DATASETS[dataset]
    before, after = percentile(samples["baseline"], 0.95), percentile(samples["current"], 0.95)
    change = round((after - before) / before * 100, 2)
    return {
        "dataset": dataset,
        "synthetic": True,
        "baseline_p95_ms": before,
        "current_p95_ms": after,
        "change_pct": change,
        "regression": change > 20,
        "sample_count": len(samples["current"]),
    }


async def sequential(value, stages):
    for stage in stages:
        value = await stage(value)
    return value


async def parallel(value, specialists):
    """TaskGroup cancels peers on failure; no partial-success release recommendation."""
    async with asyncio.TaskGroup() as group:
        tasks = {name: group.create_task(fn(value)) for name, fn in specialists.items()}
    return {name: task.result() for name, task in tasks.items()}


def route(goal):
    """Example deterministic supervisor policy; live planning is a separate boundary."""
    lowered = goal.lower()
    if "refund" in lowered:
        return "refund"
    if "mobile" in lowered or "android" in lowered:
        return "mobile_performance"
    if "release" in lowered:
        return "release"
    if "incident" in lowered:
        return "incident"
    return "knowledge"


async def performance_specialist(dataset):
    await asyncio.sleep(0)  # Cooperatively schedule independent specialists.
    return analyze(dataset)


async def security_specialist(_dataset):
    await asyncio.sleep(0)
    # Explicit fixture: not a real vulnerability scanner.
    return {"synthetic": True, "critical_findings": 0, "scanned_artifact": "fixture-release"}


async def planning_specialist(_dataset):
    return {"tasks": ["research", "coding", "analysis"], "max_specialists": 3}


async def research_specialist(documents):
    return {
        "sources": [{"id": d["id"], "source": d["source"]} for d in documents],
        "finding": "Use a 20 percent regression threshold; require human review.",
    }


async def coding_specialist(_dataset):
    # Code is a fixed trusted template, NEVER model/user-supplied source.
    source = "def hold_release(change_pct):\n    return change_pct > 20\n"
    checks = "assert not hold_release(20)\nassert hold_release(21)\nassert not hold_release(-5)\n"
    process = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-I", "-c", source + checks + "print('3 checks passed')"],
        capture_output=True,
        text=True,
        timeout=2,
        check=True,
    )
    return {
        "generated_source": source,
        "validation": process.stdout.strip(),
        "trusted_template_only": True,
    }


async def analysis_specialist(dataset):
    results = await parallel(
        dataset, {"performance": performance_specialist, "security": security_specialist}
    )
    return results


async def release_review(dataset, documents=None):
    plan = await planning_specialist(dataset)

    async def research(_):
        return await research_specialist(documents or [])

    workers = await parallel(
        dataset,
        {"research": research, "coding": coding_specialist, "analysis": analysis_specialist},
    )
    results = workers["analysis"]
    blocked = results["performance"]["regression"] or results["security"]["critical_findings"] > 0
    return {
        "specialists": {"planning": plan, **workers},
        "recommendation": "HOLD" if blocked else "PROCEED_TO_HUMAN_REVIEW",
        "synthetic": True,
    }
