# Contributing and completing labs

Keep the ten conceptual diagrams consistent with the course explanations and working examples. Put implementation-only additions in the architecture guide and update the traceability map when moving code.

Before proposing a change: describe the customer problem, preserve fixture mode, add meaningful acceptance/failure evidence, run lint/tests/evals, and update limitations. Never add real customer data, generated local credentials, private tokens or database files.

For a new tool, define typed inputs, read/write classification, allowed scenarios, scoped identity, timeout, failure semantics and approval behavior. A new external write requires a design for idempotency and reconciliation before enabling execution.

For a new learning module/lab, include the problem, concept, diagram mapping, run command, expected outcome, failure drill, deliverable and assessment criteria. Public contributions and reuse should follow the license selected by the publisher; no license is implied by this draft.
