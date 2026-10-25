"""Repeatable, synthetic teaching data. No Adobe/customer operational data."""

SCENARIOS = {
    "knowledge": "What is the rollback policy for a mobile release?",
    "incident": "Analyze the incident latency regression and propose an investigation ticket.",
    "mobile_performance": "Analyze Android mobile editor latency and propose an investigation ticket.",
    "refund": "Review invoice INV-100 for a 2500-cent refund.",
    "release": "Review release readiness using performance and security evidence.",
}


def seed(store, tenant="demo"):
    with store.transaction() as c:
        c.executemany(
            "INSERT OR IGNORE INTO documents VALUES(?,?,?,?)",
            [
                (
                    tenant,
                    "rollback",
                    "runbooks/mobile-release.md",
                    "Mobile release rollback policy: pause rollout when p95 latency regresses more than 20%. Confirm sample quality and obtain release-owner approval before rollback.",
                ),
                (
                    tenant,
                    "refund-policy",
                    "policies/refunds.md",
                    "Refund policy: verify the paid invoice, cap the example refund at 5000 cents, and require an independent reviewer. Only one local refund per invoice is supported.",
                ),
                (
                    tenant,
                    "incident-playbook",
                    "runbooks/incident.md",
                    "Incident triage: compare baseline and current latency, inspect error rate and sample size, then propose a ticket. Do not deploy or restart production from this demo.",
                ),
            ],
        )
        c.execute("INSERT OR IGNORE INTO invoices VALUES(?,?,?)", (tenant, "INV-100", 5000))
