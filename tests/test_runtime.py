import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from jev_core.models import Approval, Decision, DomainError, Principal, RunRequest
from jev_core.providers import FixturePlanner
from jev_core.runtime import Harness
from jev_core.store import Store
from jev_evals.runner import evaluate
from jev_tools.registry import Registry
from jev_workflows.scenarios import SCENARIOS


async def start(store, operator, harness, scenario="incident", key="test-key-1"):
    state = store.create(operator, RunRequest(scenario=scenario, goal=SCENARIOS[scenario]), key)
    return await harness.run(operator.tenant, state["id"])


@pytest.mark.parametrize("scenario", SCENARIOS)
async def test_scenarios(store, operator, reviewer, harness, scenario):
    state = await start(store, operator, harness, scenario)
    if state["status"] == "waiting":
        with store.connection() as c:
            assert c.execute("SELECT count(*) FROM effects").fetchone()[0] == 0
        store.approve(
            reviewer,
            state["id"],
            Approval(fingerprint=state["pending"]["fingerprint"], approve=True),
        )
        state = await harness.run(operator.tenant, state["id"])
    assert state["status"] == "succeeded"
    assert state["answer"]
    assert state["steps"] <= 8


async def test_resume_review_after_restart(store, operator, reviewer, harness):
    state = await start(store, operator, harness)
    reopened = Store(store.path)
    reopened.approve(
        reviewer, state["id"], Approval(fingerprint=state["pending"]["fingerprint"], approve=True)
    )
    other = Harness(reopened, Registry(), FixturePlanner())
    try:
        assert (await other.run(operator.tenant, state["id"]))["status"] == "succeeded"
    finally:
        other.telemetry.close()


async def test_review_fingerprint_role_and_expiry(store, operator, reviewer, harness):
    state = await start(store, operator, harness)
    with pytest.raises(DomainError, match="reviewer_required"):
        store.approve(
            operator,
            state["id"],
            Approval(fingerprint=state["pending"]["fingerprint"], approve=True),
        )
    with pytest.raises(DomainError, match="self_approval"):
        store.approve(
            Principal(tenant="alpha", subject="alice", role="reviewer"),
            state["id"],
            Approval(fingerprint=state["pending"]["fingerprint"], approve=True),
        )
    with pytest.raises(DomainError, match="payload_mismatch"):
        store.approve(reviewer, state["id"], Approval(fingerprint="0" * 64, approve=True))
    with store.transaction() as c:
        c.execute(
            "UPDATE runs SET state=json_set(state,'$.pending.expires',0) WHERE id=?", (state["id"],)
        )
    with pytest.raises(DomainError, match="approval_expired"):
        store.approve(
            reviewer,
            state["id"],
            Approval(fingerprint=state["pending"]["fingerprint"], approve=True),
        )


async def test_rejection_has_no_effect(store, operator, reviewer, harness):
    state = await start(store, operator, harness)
    store.approve(
        reviewer, state["id"], Approval(fingerprint=state["pending"]["fingerprint"], approve=False)
    )
    assert (await harness.run("alpha", state["id"]))["status"] == "rejected"
    with store.connection() as c:
        assert c.execute("SELECT count(*) FROM tickets").fetchone()[0] == 0


async def test_concurrent_review_exactly_one_local_effect(store, operator, reviewer, harness):
    state = await start(store, operator, harness)
    approval = Approval(fingerprint=state["pending"]["fingerprint"], approve=True)

    def review():
        try:
            store.approve(reviewer, state["id"], approval)
            return "ok"
        except DomainError as exc:
            return exc.code

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(lambda _: review(), range(2)))
    assert sorted(outcomes) == ["not_awaiting_review", "ok"]
    with store.connection() as c:
        assert c.execute("SELECT count(*) FROM tickets").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM effects").fetchone()[0] == 1


async def test_refund_revalidation_and_atomic_rollback(store, operator, reviewer, harness):
    state = await start(store, operator, harness, "refund")
    with store.transaction() as c:
        c.execute("UPDATE invoices SET paid_cents=100 WHERE tenant='alpha'")
    with pytest.raises(DomainError, match="refund_not_eligible"):
        store.approve(
            reviewer,
            state["id"],
            Approval(fingerprint=state["pending"]["fingerprint"], approve=True),
        )
    assert store.get("alpha", state["id"])["status"] == "waiting"
    with store.connection() as c:
        assert c.execute("SELECT count(*) FROM effects").fetchone()[0] == 0


async def test_duplicate_refund_blocked_across_runs(store, operator, reviewer, harness):
    for index in range(2):
        state = await start(store, operator, harness, "refund", f"refund-{index}")
        approval = Approval(fingerprint=state["pending"]["fingerprint"], approve=True)
        if index:
            with pytest.raises(DomainError, match="already_refunded"):
                store.approve(reviewer, state["id"], approval)
        else:
            store.approve(reviewer, state["id"], approval)


def test_idempotency_and_tenant_isolation(store, operator):
    req = RunRequest(scenario="knowledge", goal="rollback policy")
    a = store.create(operator, req, "same-key")
    assert store.create(operator, req, "same-key")["id"] == a["id"]
    with pytest.raises(DomainError, match="idempotency_conflict"):
        store.create(operator, RunRequest(scenario="knowledge", goal="different"), "same-key")
    with pytest.raises(DomainError, match="not_found"):
        store.get("beta", a["id"])
    with pytest.raises(DomainError, match="not_found"):
        store.events("beta", a["id"])


def test_lease_recovery_and_fencing(store, operator):
    state = store.create(
        operator, RunRequest(scenario="knowledge", goal="rollback policy"), "lease-key"
    )
    first, token = store.claim("alpha", state["id"])
    with pytest.raises(DomainError, match="busy"):
        store.claim("alpha", state["id"])
    with store.transaction() as c:
        c.execute("UPDATE runs SET lease_until=?", (time.time() - 1,))
    _, replacement = store.claim("alpha", state["id"])
    assert replacement != token
    with pytest.raises(DomainError, match="lease_lost"):
        store.checkpoint("alpha", first, token, "invalid")


class RepeatPlanner:
    async def decide(self, _context):
        return Decision(kind="tool", tool="search_knowledge", arguments={"query": "rollback"})


async def test_loop_budget(store, operator, harness):
    harness.planner, harness.max_steps = RepeatPlanner(), 3
    state = await start(store, operator, harness, "knowledge")
    assert state["error"] == "step_budget_exceeded"
    assert state["steps"] == 3


async def test_timeout(store, operator, harness):
    class Slow:
        async def decide(self, _context):
            await asyncio.sleep(1)

    harness.planner, harness.timeout = Slow(), 0.01
    assert (await start(store, operator, harness, "knowledge"))["error"] == "TimeoutError"


async def test_cancellation_resumable(store, operator, harness):
    class Interrupted:
        async def decide(self, _context):
            raise asyncio.CancelledError

    harness.planner = Interrupted()
    with pytest.raises(asyncio.CancelledError):
        await start(store, operator, harness, "knowledge")
    with store.connection() as c:
        assert c.execute("SELECT json_extract(state,'$.status') FROM runs").fetchone()[0] == "ready"


@pytest.mark.parametrize(
    "decision,error",
    [
        (Decision(kind="tool", tool="shell", arguments={"command": "echo hi"}), "tool_not_allowed"),
        (
            Decision(
                kind="tool",
                tool="issue_refund",
                arguments={"invoice": "INV-100", "amount_cents": 1},
            ),
            "tool_not_allowed",
        ),
        (
            Decision(kind="final", answer="Invented", citations=["nonexistent"]),
            "unsupported_citations",
        ),
        (Decision(kind="final", answer="No citations"), "citations_required"),
    ],
)
async def test_adversarial_decisions(store, operator, harness, decision, error):
    class Bad:
        async def decide(self, _context):
            return decision

    harness.planner = Bad()
    assert (await start(store, operator, harness, "knowledge"))["error"] == error


async def test_eval_gate_detects_bad_planner():
    class Wrong:
        async def decide(self, _context):
            return Decision(kind="final", answer="Incorrect")

    assert (await evaluate())["gate"]
    assert not (await evaluate(Wrong()))["gate"]
