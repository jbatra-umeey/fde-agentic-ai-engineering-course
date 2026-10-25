# From prototype to customer deployment

Audience: software engineers moving toward Forward Deployed Engineering, solution engineers who want stronger implementation skills, and technical leads building customer-specific AI workflows.

Outcome: demonstrate that you can discover a real problem, implement an agent solution, explain its limits, measure it, and hand it over to an accountable owner. Memorizing framework names is not the goal.

## Prerequisites and preflight

You should be comfortable with Python functions/classes, JSON, HTTP, Git, SQL and basic automated tests. If any are unfamiliar, spend a preparation week building a small authenticated CRUD API first. No previous agent framework experience is required.

Preflight: create a virtual environment, install the project, run `jev lesson 1`, `pytest -q` and `jev-eval`. Inspect one run's observations and explain why a tool result is different from a model assertion. Keep a learning journal in a separate personal branch; do not add real customer information.

## Three suggested paths

| Path | Suggested effort | Deliverable |
|---|---|---|
| Explore | 4–6 hours | Run all ten lessons and explain their arrows |
| Practitioner | 20–30 hours | Complete module labs, tests and failure exercises |
| FDE portfolio | 40–60 hours | Complete discovery, capstone, deployment evidence and handover |

These are planning estimates, not completion guarantees. Progress is assessed by evidence and teach-back.

## Six-week portfolio sequence

| Week | Modules | Customer milestone |
|---|---|---|
| 1 | Discovery + 1 Harness + 2 Loops | Scope a measurable workflow and demo the happy path |
| 2 | 3 Context + 4 Tools | Prove source ownership, API contracts and integration boundaries |
| 3 | 5 Memory + 6 Orchestration | Justify state retention and task decomposition |
| 4 | 7 Guardrails + 8 Evals | Demonstrate misuse resistance and an evidence-based release gate |
| 5 | 9 Human review + 10 Observability | Recover from failures and operate the workflow |
| 6 | Capstone + stakeholder demo | Deliver a staged pilot, limitations and support handover |

## Module completion contract

For every module, read the matching photo-aligned guide, run its lesson, complete its lab, demonstrate its failure case and submit the named artifact. Add a short decision record with: customer constraint, alternatives, selected design, evidence, tradeoff and reversal trigger.

Pair exercise: one learner is the customer sponsor, one is the FDE, and one is the operator/security reviewer. Rotate roles. The sponsor must ask about measurable value, the operator about recovery, and the reviewer about permissions and data exposure.

## Assessment

Use the [capstone rubric](CAPSTONE.md). A polished demo does not compensate for cross-tenant access, unapproved effects or misleading claims. Learners must distinguish tested fixture behavior, mocked-provider contracts, live integration evidence and deployment assumptions.

Every module's reference solution is in the linked implementation and its executable lesson. A lab intentionally changes the scenario so learners must apply the concept rather than copy the solution verbatim.
