# Production-oriented inference architecture

The original ten modules and illustrations remain the conceptual foundation. This additive implementation connects live inference to their existing runtime. The supplied starter overlay was applied first; its CLI switches were retained and its shared `last_usage` logging was replaced with per-run accounting for concurrency safety.

```mermaid
flowchart TD
  API["API and CLI"] --> Harness["Bounded harness"]
  Harness --> Context["Scoped context and versioned prompts"]
  Context --> Router["Operator model routes"]
  Router --> OpenAI["OpenAI or compatible HTTP"]
  Router --> Claude["Anthropic Messages"]
  OpenAI --> Decision["Validated Decision"]
  Claude --> Decision
  Decision --> Registry["Scenario tool authorization"]
  Registry --> Reads["Read tools"]
  Registry --> Approval["Independent approval"]
  Approval --> Ledger["Transactional local effect"]
  Registry --> Agents["LLM release specialists"]
  Agents --> Router
  Reads --> Harness
  Ledger --> Harness
  Harness --> Store["Fenced state and usage"]
  Router --> OTel["OTel spans and metrics"]
```

## Planning, fallback and recovery

```mermaid
sequenceDiagram
  participant H as Harness
  participant R as Model router
  participant P as Provider
  participant T as Tool registry
  participant S as State store
  H->>S: Reserve planning step
  H->>R: Context and typed output schema
  R->>S: Reserve model attempt
  R->>P: Versioned prompt and untrusted data
  alt Transient error or invalid output
    P-->>R: Failure
    R->>S: Record sanitized failure metadata
    R->>P: Bounded retry or configured fallback
  end
  P-->>R: Structured Decision and usage
  R->>S: Record tokens, latency and estimated cost
  R-->>H: Validated Decision
  H->>T: Authorize name and validate arguments
  alt Invalid arguments
    T-->>H: Sanitized recoverable error
    H->>S: Checkpoint recovery within original budget
  else Read tool
    T-->>H: Scoped observation
    H->>S: Checkpoint observation
  else Write proposal
    H->>S: Persist fingerprint and wait for reviewer
  end
```

The provider can format a candidate action; only the registry grants tool access. Provider failures never invoke business tools. The run's ContextVar isolates usage between requests while sharing a recorder among that run's concurrent specialist tasks. Every model attempt consumes a durable reservation before network I/O.

## Live release review

```mermaid
flowchart TD
  Evidence["Synthetic metrics and scoped documents"] --> Supervisor["LLM supervisor creates typed tasks"]
  Supervisor --> Research["Research specialist"]
  Supervisor --> Coding["Coding specialist"]
  Supervisor --> Analysis["Analysis specialist"]
  Supervisor --> Security["Security specialist"]
  Research --> Join["TaskGroup join and citation validation"]
  Coding --> Join
  Analysis --> Join
  Security --> Join
  Join --> Policy["Deterministic release policy"]
  Policy --> Hold["HOLD when evidence is missing"]
  Policy --> Review["Recommendation for human review"]
```

Analysis and security are required unique roles; research/coding are optional model-selected tasks. TaskGroup cancels peers on a failure. Reports are bounded schemas with risk, missing evidence and source IDs. Suggested code remains inert text. The course supplies no real security scan, so the live release path returns HOLD even if all models are optimistic. The final run exposes `release_recommendation` from the tool policy as the authoritative structured decision; free-form answer text is advisory. The original offline specialist/template example remains available to teach the contrast.

## Evaluation and release gates

```mermaid
flowchart TD
  Dataset["Versioned golden and adversarial cases"] --> Runner["Fixture or live harness"]
  Runner --> Rules["Outcome, trajectory, approval and budget checks"]
  Runner --> Judge["Separately routed LLM judge"]
  Rules --> Gate["All required checks must pass"]
  Judge --> Gate
  Baseline["Previous case-level report"] --> Gate
  Gate --> Artifact["Versioned validation artifact"]
```

Judge output cannot turn a failed deterministic check into a pass. Refusal or invalid judge output fails its gate. Golden cases are synthetic regression data, not evidence of generalized customer quality. No chain-of-thought is requested or stored; evaluation uses observable actions, evidence and final answers.

## Deployment boundary

```mermaid
flowchart TD
  Client["Authenticated operator or reviewer"] --> Ingress["TLS ingress: deployment responsibility"]
  Ingress --> API["One non-root API container"]
  API --> SQLite["Persistent SQLite volume"]
  API --> Providers["Approved HTTPS model providers"]
  API --> Collector["Optional OTLP collector"]
  CI["Credential-free pull-request CI"] --> Image["Validated wheel and container"]
  Image --> API
```

This is a bounded single-process reference. Customer ingestion, remote side-effect reconciliation, OIDC, distributed scheduling, monetary quotas and high availability require deployment-specific engineering. See the [readiness matrix](PRODUCTION_READINESS.md).
