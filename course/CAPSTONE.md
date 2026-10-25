# Capstone: a customer-ready pilot dossier

Choose one track. The stakeholder details below are fictional teaching briefs, not customer requirements already validated.

| Track | Sponsor problem | Initial workflow | High-risk boundary |
|---|---|---|---|
| Mobile release operations | Engineers spend too long collecting regression evidence | Runbook retrieval → metrics → reviewed ticket | No automatic rollback |
| Service reliability | Repeated latency incidents overwhelm responders | Evidence gathering → parallel analysis → escalation proposal | No restarts or deployments |
| Customer support | Refund decisions are inconsistent | Invoice lookup → policy retrieval → reviewed refund proposal | No unapproved payment action |

## Required delivery

1. Interview a peer acting as sponsor and complete the discovery template. Record unknowns explicitly.
2. Define a measurable acceptance rubric and scope one workflow.
3. Map all ten course diagrams to your workflow. Preserve each module's conceptual flow; identify any inapplicable capability and justify it instead of inventing a need.
4. Add one real sandbox integration using a dedicated adapter. Keep the existing synthetic path and prove both contracts. Never use production money or production deployment privileges in the course.
5. Add at least 15 labeled cases: happy path, missing evidence, conflicting evidence, malformed action, tenant boundary, duplicate request, provider timeout, review rejection and recovery.
6. Demonstrate independent review, retry/idempotency semantics and restart behavior.
7. Produce a deployment record with environment, dependency lock, image identifier, configuration sources, executed checks and rollback steps.
8. Deliver an operations runbook and a seven-minute stakeholder demo.

No API credentials available? Use a local sandbox service you implement, record the limitation and demonstrate network-level error/recovery behavior. Do not relabel a mock as a real third-party integration.

## Scoring rubric

| Dimension | Points | Evidence |
|---|---:|---|
| Discovery and value | 15 | Current workflow, measured/proposed baseline distinction, scope and owners |
| Architecture and diagram fidelity | 15 | All ten mappings, trust boundaries and justified choices |
| Implementation and integration | 20 | Runnable slice, typed contracts, safe effects and dependency control |
| Evaluation and adversarial behavior | 20 | Labeled cases, meaningful gate, failure analysis and held-out data |
| Reliability and operations | 15 | Recovery, tracing, backup/restore and rollback evidence |
| Communication and handover | 15 | Clear demo, teach-back, limitations and operator ownership |

Suggested completion threshold: 80/100, with no critical failure. Critical failures are cross-tenant disclosure, unapproved consequential effects, exposed credentials or fabricated verification claims. This is a course assessment recommendation, not an accredited certification.

## Acceptance demonstration

Present a success, a rejection, an expired approval, a provider outage and a duplicate request. Explain exactly what was persisted at every boundary. Show a changed evaluation failing CI. Give the receiving operator the runbook and ask them to diagnose one fault without your help.

## Stretch work

After the core acceptance evidence is complete, consider OIDC, PostgreSQL with row-level security, a durable queue/outbox, semantic retrieval, live specialist models, distributed tracing across resumed runs, cost accounting, or a domain-specific review interface. Each extension needs its own threat model and validation.
