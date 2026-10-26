# Live systems practicum: all ten modules

Complete the [live setup](../../docs/LIVE_INFERENCE.md) first. Start with fixtures, then repeat applicable exercises using explicit live mode. Record the commit, prompt hash, model route, dataset version, observed behavior and cost completeness for every experiment. Use synthetic data and an explicit provider budget.

| Module | Executable starting point | Exercise and acceptance criteria |
|---|---|---|
| 1. Harness | `jev lesson 1 --live` | Compare fixture/live output; deliberately misconfigure a key. Confirm failure is explicit and never becomes fixture success. |
| 2. Loop | `jev lesson 2 --live` | Observe read→proposal→waiting; inject invalid arguments in a test planner. Prove two recoveries maximum and durable step accounting. |
| 3. Context | `jev lesson 3` | Add an instruction-like document and inspect its untrusted evidence position; repeat `jev demo --scenario knowledge --live`. Demonstrate tenant isolation and context size cap. |
| 4. Tools | `jev lesson 4` | Add a narrow read-only tool, schema and scenario allowlist. Test invalid types, extra fields, timeout and forbidden cross-scenario use before enabling it. |
| 5. Memory | `jev lesson 5 --live` | Verify consent creates scoped memory, deletion clears it, and remembered text never becomes system instructions. Document database retention limits. |
| 6. Orchestration | `jev lesson 6 --live` | Inspect LLM supervisor tasks and parallel reports. Change security route to the second provider. A failed specialist must fail the workflow; missing scan evidence must HOLD. |
| 7. Guardrails | `jev lesson 7` | Run injected model-action tests. Demonstrate forged approval in a goal cannot authorize a write. Document controls that remain outside model prompts. |
| 8. Evals | `jev lesson 8 --live` | Run golden+adversarial gates and a separately routed judge. Introduce one bad answer, verify failed exit status, then compare case-level baseline results. |
| 9. Human review | `jev lesson 9 --live` | Trace fingerprint creation and simulated review, then use two API identities. Change arguments after proposal and prove rejection with no effects. |
| 10. Observability | `jev lesson 10 --live` | Inspect provider spans and per-call metadata. Configure prices, compare estimates with unknown pricing, verify no prompt/key appears in spans and export to a collector. |

Lessons 3, 4 and 7 are intentionally deterministic context/tool/policy inspections; `--live` does not make an unnecessary inference call in them. Lessons 1, 2, 5, 9 and 10 use the live harness; lesson 6 uses LLM specialists; lesson 8 uses live evaluation and the real judge. CLI lesson 9 explicitly simulates an independent reviewer for teaching. The API does not simulate approval.

## Capstone: customer release assistant

1. Define a customer's release acceptance rubric, identity boundary and data destinations.
2. Add a versioned real read connector with a bounded output schema and a recorded contract test. Keep fixture mode available.
3. Replace synthetic scan input with authenticated scan evidence. Keep HOLD for unavailable or stale scans.
4. Collect at least 20 held-out cases with independently labeled expected outcomes. Separate development cases from final acceptance cases.
5. Compare two configured routes for quality, p50/p95 latency, completion rate, token usage and estimated cost. Report unknown usage separately.
6. Run failure drills: throttling, provider outage, schema violation, malicious evidence, worker cancellation and reviewer expiry.
7. Deliver a PR with tests, diagrams, deployment/rollback instructions and an evidence-based readiness decision. Do not claim a deployment or connector is verified without its execution record.

## Instructor checkpoints

Ask learners why an LLM refusal must not be bypassed by provider fallback, why a valid JSON schema is not authorization, why usage must be scoped to a run under concurrency, and why exact local transaction semantics do not establish remote exactly-once delivery. Require a demonstration, not only an explanation.
