# Implementation architecture

The [concept map](CONCEPT_MAP.md) connects the ten disciplines to their implementation. The diagrams below show how the components work together; the [illustrated guide](illustrations/README.md) introduces each concept.

## Components and trust boundaries

```mermaid
flowchart TD
  U["Operator or reviewer"] --> API["FastAPI: identity and request validation"]
  CLI["CLI: synthetic teaching identity"] --> H["Harness: budgets and state transitions"]
  API --> H
  H --> C["Context: rules, evidence and memory"]
  C --> P["Planner: fixture or configured HTTP model"]
  P --> V["Decision and tool validation"]
  V --> R["Read tools and specialist workers"]
  V --> W["Pending write proposal"]
  W --> API
  API --> A["Independent review transaction"]
  R --> DB["SQLite: tenant-scoped state"]
  A --> DB
  H --> DB
  H --> T["OpenTelemetry spans and structured events"]
```

The model receives no database handle, tenant override, authentication token or arbitrary network tool. Server-side code injects identity. Retrieved content and memory are always untrusted input. Optional model requests send the assembled context to the configured provider; deployment owners must approve that data destination.

## Successful reviewed action

```mermaid
sequenceDiagram
  participant O as Operator
  participant H as API and harness
  participant P as Planner and tools
  participant D as Durable store
  participant R as Reviewer
  O->>H: Goal and idempotency key
  H->>D: Create run or return existing run
  H->>D: Claim lease and reserve step
  H->>P: Plan using scoped context
  P-->>H: Read result then proposed write
  H->>D: Persist waiting state and fingerprint
  H-->>O: Proposed output for review
  R->>H: Approve exact fingerprint
  H->>D: Verify role, tenant, owner and expiry
  Note over H,D: One local transaction
  H->>D: Write effect, ledger and ready checkpoint
  H->>P: Continue with observed committed effect
  P-->>H: Final answer
  H->>D: Persist succeeded state
  H-->>R: Final result
```

If the process stops after approval commits but before final planning, the run remains ready. Resuming sees the effect observation already recorded. Local effect creation and approval cannot partially commit. This guarantee does not extend to remote services.

## State machine

```mermaid
stateDiagram-v2
  [*] --> ready
  ready --> running: claim lease
  running --> running: validated read and checkpoint
  running --> waiting: write proposal
  waiting --> ready: independent approval and local effect
  waiting --> rejected: reviewer rejects
  running --> succeeded: valid final output
  running --> failed: timeout, invalid decision or budget
  running --> ready: cooperative interruption
  running --> running: reclaim expired lease
  succeeded --> [*]
  rejected --> [*]
  failed --> [*]
```

Waiting approvals have a one-hour TTL. An expired review request returns a conflict and leaves the historical proposal intact; an operator must create a new request/key for a new proposal. Failed runs are terminal, preserving diagnostics. A killed worker's lease expires after 45 seconds; the owner can resume with the remaining durable step budget.

## Deployment topology

```mermaid
flowchart TD
  Client["Customer client"] --> Ingress["TLS ingress: required for remote use"]
  Ingress --> API["Single API instance"]
  Config["Secret-managed identity and model configuration"] --> API
  API --> Volume["Local persistent volume: SQLite WAL"]
  API --> Model["Optional approved HTTPS model endpoint"]
  API --> Collector["Optional OTLP HTTP collector"]
  Collector --> Backend["Trace backend: customer choice"]
  Volume --> Backup["SQLite backup and tested restore"]
```

The provided Compose file binds only to loopback and uses one API worker. TLS ingress, collector, trace backend and external model are not provisioned by the default stack. Do not mount SQLite on a shared network filesystem or scale API replicas without redesigning persistence and coordination.

## State and data model

| Table | Scope and purpose |
|---|---|
| `runs` | Tenant and creator scoped idempotency, serialized request/state, lease |
| `events` | Tenant/run correlated metadata; no prompts or raw provider errors |
| `documents` | Tenant-scoped source IDs and externally maintained content |
| `memory` | Tenant/user/session or cross-session opt-in summaries with TTL |
| `effects` | Tenant/run/step ledger binding approval fingerprint to local result |
| `tickets`, `invoices`, `refunds` | Local example business records |
| `rate_limits` | Per-tenant/user fixed-window counters shared by local processes |

## Failure semantics

| Failure | Behavior | Recovery |
|---|---|---|
| Model timeout or malformed response | Failed run with sanitized error code | Fix cause; submit a new request/key |
| Retryable model HTTP response | Up to three bounded attempts under outer deadline | No write retries are implied |
| Invalid or forbidden tool | Fail closed | Correct contract or authorized scope |
| Concurrent execution | One lease owner; other caller gets conflict | Read run or retry after lease expiry |
| Concurrent review | One local transaction wins | Read final state; do not duplicate business action |
| Invoice changed before review | Revalidate amount at commit | Review updated business state |
| Specialist failure | Cancel peer tasks and fail the run | Diagnose failed specialist before rerun |
| Process kill | Durable checkpoints survive; lease eventually expires | Owner calls resume |
| Storage outage | Request may fail before durable completion | Restore storage; inspect state before retry |

## Source references

The implementation uses [FastAPI testing patterns](https://fastapi.tiangolo.com/advanced/async-tests/), [SQLite transaction semantics](https://www.sqlite.org/lang_transaction.html), [SQLite isolation guidance](https://www.sqlite.org/isolation.html), and [OpenTelemetry Python instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/). Links document underlying primitives; they do not certify this application.
