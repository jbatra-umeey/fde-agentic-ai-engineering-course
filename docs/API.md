# API walkthrough

Start the service using the README. The generated `.env` contains operator, reviewer and reader credentials for the synthetic `demo` tenant. A production deployment should replace these teaching identities with the organization's authentication and authorization model.

## Create a proposed action

```bash
curl -sS http://127.0.0.1:8000/v1/runs \
  -H "Authorization: Bearer $JEV_OPERATOR_TOKEN" \
  -H 'Idempotency-Key: incident-demo-0001' \
  -H 'Content-Type: application/json' \
  -d '{"scenario":"incident","goal":"Investigate the latency regression","session":"workshop","remember":false}'
```

The response should have `status: waiting`, an `id`, metrics observations and a `pending` action with exact arguments, fingerprint and expiry. Record the ID and inspect the proposal. There is no ticket until review. Repeating the same key and payload returns the existing run; using the same key with a changed payload returns 409.

## Review the exact output

Set `RUN_ID` and `FINGERPRINT` to the values you actually received, then:

```bash
curl -sS "http://127.0.0.1:8000/v1/runs/$RUN_ID/review" \
  -H "Authorization: Bearer $JEV_REVIEWER_TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"fingerprint\":\"$FINGERPRINT\",\"approve\":true}"
```

Use `approve: false` to reject. The reviewer cannot change the action through this endpoint. A different action needs a new proposal and review. A second submission after a completed review returns 409; this is intentional replay protection.

## Inspect and recover

| Method and path | Purpose | Authorization |
|---|---|---|
| `GET /healthz` | Database liveness | Public; no sensitive data |
| `POST /v1/runs` | Create and execute to a stop condition | Operator |
| `GET /v1/runs/{id}` | Run state and proposal | Any authenticated identity in tenant |
| `GET /v1/runs/{id}/events` | Durable event metadata | Any authenticated identity in tenant |
| `POST /v1/runs/{id}/review` | Approve/reject exact proposal | Independent reviewer in tenant |
| `POST /v1/runs/{id}/resume` | Resume ready/interrupted work | Original operator |
| `DELETE /v1/memory` | Forget caller's memory | Authenticated caller |
| `GET /v1/metrics` | Tenant run counts by status | Authenticated caller |

Tenant members intentionally share run visibility in this reference. If a customer needs case-level confidentiality, implement per-resource ACLs before loading that data.

## Error contract

Errors return `{"error":"stable_code"}`. Important responses: 401 unauthorized, 403 insufficient permission, 404 unknown or other-tenant run, 409 idempotency/review/lease conflict, 413 body limit, 422 invalid schema/business input, and 429 rate limit. Model/tool execution errors are durable failed run states; a transport-level 200 does not mean task success. Check `status` and the evaluation criteria.

## Optional live-model mode

Set `JEV_PLANNER=http`, `JEV_MODEL_ENDPOINT` to an approved HTTPS chat-completions-compatible endpoint, `JEV_MODEL` to a supported model name, and `JEV_MODEL_KEY` through your secret manager. The adapter sends JSON-mode requests and expects a typed Decision in the response's first message.

The endpoint must support the request fields used in `HTTPPlanner`. Compatibility with a specific hosted model has not been established by fixture or mock-transport tests. Use a dedicated development account, inspect actual tool trajectories, verify data handling and run the customer evaluation set before enabling writes.

There are no built-in provider names, live credentials or arbitrary user-configurable endpoints. The operator controls egress configuration. The API and CLI fixture demo are separate paths; `jev demo` always remains synthetic.
