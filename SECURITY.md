# Security model and limits

The reference demonstrates deterministic authorization and safe local effects. It does not claim a complete content-safety system, secure arbitrary-code sandbox, regulatory compliance or production penetration testing.

## Enforced controls

- High-entropy bearer credentials are represented by hashes in server identity configuration. Request payloads cannot choose tenant or role.
- Every run/document/invoice/memory read is scoped to an authenticated tenant; memory also scopes to subject and session.
- Scenario-specific tool allowlists reject unsupported capabilities. Pydantic rejects extra fields and validates types and bounds.
- Consequential writes require a different reviewer subject, matching tenant, unexpired proposal and exact fingerprint.
- The fingerprint binds tenant, run, step, tool and arguments. Local effects, approval ledger and resumed state share a transaction.
- Per-subject request limits, actual-body byte limits, step budgets, invocation deadlines and read-tool timeouts bound workload.
- There is no shell/URL tool. The coding specialist executes a fixed developer-owned template only; arbitrary generated code is never accepted.
- Provider configuration requires HTTPS, disables redirects and environment proxy inheritance, bounds response bytes and retries only eligible model requests.
- Telemetry excludes prompts, output bodies and raw exception messages. Validation errors do not echo submitted input.

## Threat model

| Threat | Mitigation | Remaining boundary |
|---|---|---|
| Prompt injection in retrieved content | Untrusted context compartment, server-side tool policy | Model can still produce misleading prose; needs live adversarial evaluation |
| Cross-tenant retrieval or run access | Tenant-scoped SQL and server identity | Same-tenant members share run visibility |
| Unapproved refund/ticket | Independent exact-payload review | Compromised reviewer or host remains privileged |
| Duplicate local action | Transactional effect ledger and unique business key | Remote APIs need outbox/reconciliation |
| Resource exhaustion | Body/rate/step/time limits | TLS ingress must enforce connection and slow-body limits; no global queue limit |
| Secret leakage via exceptions | Sanitized codes and metadata-only traces | Database contains user-supplied content; generated text has no comprehensive DLP filter |
| Memory poisoning | Opt-in, expiry, identity scope, untrusted-data placement | No separate semantic memory-review workflow |
| Provider exfiltration | Operator-approved static endpoint and scoped context | Deployment must approve data classification and egress |

## Before a real customer deployment

Integrate the customer's identity provider, resource ACLs, secrets manager, TLS ingress, encryption, retention policy and incident response process. Perform threat modeling and adversarial testing with the actual model and datasets. Add a true sandbox if accepting untrusted generated code. Use isolated compute with strict network/filesystem/resource controls; Python `-I` alone is not such a sandbox.

Use the production-readiness matrix to track owners and evidence. Report vulnerabilities privately to the eventual repository owner's chosen contact; add that contact before publication. Never attach real secrets or customer data to public issues.

## Live inference upgrade boundaries

Model endpoints/routes are trusted operator configuration. Fallback must satisfy the same customer data-handling policy as the primary provider. Provider refusals and auth failures never trigger fallback. Raw provider bodies and rejected arguments are excluded from event/trace metadata. Costs are estimates, not monetary enforcement. Live suggested code is inert text; it is never passed to the fixture's trusted-template subprocess. `release_recommendation` is the authoritative structured policy decision; model prose is advisory. See [live configuration](docs/LIVE_INFERENCE.md) and [evaluation limits](docs/EVALUATION.md).
