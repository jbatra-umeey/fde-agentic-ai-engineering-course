# Production readiness: evidence, not labels

This repository is a course and a runnable engineering reference. Production-oriented controls are implemented, but a deployment-specific review is still required. The exact executed checks are recorded in [VALIDATION.md](../reports/VALIDATION.md).

| Area | Implemented baseline | Remaining work before customer launch |
|---|---|---|
| Harness and loops | Typed decisions, durable steps, limits, lease fencing | Load testing, global concurrency and budget policies |
| Context | Tenant-scoped lexical retrieval, source IDs, byte cap | Customer source ingestion, freshness, per-document ACLs and retrieval-quality tests |
| Tools | Narrow typed registry and deterministic authorization | Real connectors, contract tests, rate limits and remote failure semantics |
| Memory | Opt-in, subject/session scope, TTL and delete | Data governance, sensitive-data filtering and full historical deletion |
| Orchestration | Sequential, parallel, router, four specialist roles | Live specialist models and deployment-specific reliability tests if required |
| Human review | Exact-payload independent approval and atomic local effects | Reviewer notification, queue ownership, escalation and approval-expiry UX |
| Identity | Hashed static-token map and roles | OIDC/service identity, key rotation process, fine-grained ACLs |
| Persistence | SQLite WAL, transactional local effects, schema check | Backup/restore drills, migration strategy; PostgreSQL/queue if scale demands |
| Evals | Five synthetic cases and negative/security tests | Real labeled corpus, held-out set, live-model repeats and calibrated rubric |
| Observability | Structured events, tenant status metrics, OTel spans/exporter | Confirm collector delivery, dashboards, alerts, retention and runbooks |
| Packaging | Version-pinned dependencies, Dockerfile, Compose, CI definition | Verify image build/run, pin image digest, dependency/container vulnerability review |
| Live model | HTTPS adapter and mock transport contract tests | Actual provider compatibility, quality, cost and privacy validation |
| Documentation | Ten photo-aligned lessons, field guide, capstone and operations | Learner pilot, publication rights review and chosen license |

## Guarantees deliberately not claimed

No proof of semantic factuality, prompt-injection immunity, distributed exactly-once execution, arbitrary-code isolation, high availability, production SLO achievement, payment processing, Jira integration or compliance certification. Citation-ID validation proves provenance membership, not that a sentence is entailed by its citation.

## Release decision

Use the handover template to record owner, evidence and status for each remaining item. Enable a restricted customer pilot only after its scoped acceptance criteria pass. Expand permissions and traffic incrementally, with rollback criteria defined in advance.
