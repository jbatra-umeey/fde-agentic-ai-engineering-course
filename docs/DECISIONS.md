# Architecture decision records

## ADR 001 — Explicit Python loop

Decision: implement the bounded loop directly instead of requiring a particular orchestration framework. Reason: learners can trace every decision, persistence boundary and authorization check. Tradeoff: the project must own recovery semantics and has fewer built-in integrations. Revisit when distributed scheduling, graph visualization or complex durable branching warrants a framework. Keep security and business-effect contracts outside model/framework callbacks.

## ADR 002 — One distribution, multiple ownership boundaries

Decision: use `apps` and `packages` directories in one monorepo and publish one Python distribution. Reason: fast setup, consistent types and one tested dependency set. Tradeoff: package versions cannot evolve independently. Split distributions when teams need separate release cadence, not merely to increase folder count.

## ADR 003 — SQLite for the reference deployment

Decision: use short `BEGIN IMMEDIATE` transactions and WAL for a local persistent store. Reason: no external service is needed to teach restart, concurrency and atomic effects. Tradeoff: synchronous database work and a single writer limit throughput. Never hold a transaction across network calls. Use PostgreSQL and a durable scheduler/outbox when moving to multiple hosts or higher write volume.

## ADR 004 — Fixture first, live model opt-in

Decision: keep deterministic fixtures as the default and provide a separate configurable HTTPS planner. Reason: repeatable education and CI without credentials or unpredictable spend. Tradeoff: fixture success does not establish real model quality. Mock tests validate the adapter contract only. Run customer evaluations with the chosen live provider before pilot approval.

## ADR 005 — Proposals precede consequential effects

Decision: use an output→human-review flow, interpreting the first output as a proposal. Reason: review must happen before an irreversible effect. Tradeoff: reviewer latency and queue ownership become part of the system. Do not bypass the gate for a faster demo.

## ADR 006 — Local atomicity, explicit remote boundary

Decision: local ticket/refund examples use the same transaction as the effect ledger and checkpoint. Reason: demonstrate concrete replay safety. Tradeoff: the pattern cannot atomically commit a remote service call. A remote adapter must use a transactional outbox, stable operation key, downstream idempotency and reconciliation.
