# Live inference and model operations

The API, CLI and harness-based lessons use the same provider, tool-authorization and approval boundaries. Fixture mode is the default and performs no model requests. Live mode runs actual HTTPS requests and can incur provider charges. Business data remains synthetic unless an operator explicitly replaces the seeded sources.

## Install and run offline

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
jev demo --simulate-review
jev lesson 6
jev-eval --adversarial --output reports/adversarial-evaluation.json
```

## Configure providers

Copy [models.example.json](../config/models.example.json) to `config/models.local.json`. Replace model placeholders with model IDs enabled for your accounts. This file is ignored by Git. Supply both named keys through environment variables or a secret manager; keys are never stored in routing JSON. All configured models are validated at startup, including their key availability. For a single provider, remove the secondary model and replace every route containing `secondary` with `primary`.

```bash
cp config/models.example.json config/models.local.json
# Edit model IDs and routes before proceeding.
# Enter keys without including their values in shell history:
read -rsp 'OpenAI key: ' OPENAI_API_KEY; echo
export OPENAI_API_KEY
read -rsp 'Anthropic key: ' ANTHROPIC_API_KEY; echo
export ANTHROPIC_API_KEY
export JEV_PLANNER=router
export JEV_MODELS_CONFIG=config/models.local.json
jev demo --scenario knowledge --live
jev demo --scenario release --live
jev lesson 6 --live
jev lesson 10 --live
```

`--live` rejects fixture configuration. Omitting `--live` keeps CLI examples offline even if the environment selects a live planner. API mode follows `JEV_PLANNER` at application startup. Fixture mode never becomes an automatic live-provider fallback.

| Protocol | Request | Structured result | Credential |
|---|---|---|---|
| `openai` | Chat Completions; `max_completion_tokens` | Forced `emit_result` function call | Bearer key; host restricted to `api.openai.com` |
| `anthropic` | Messages; version `2023-06-01` | Forced `emit_result` tool-use block | `x-api-key`; host restricted to `api.anthropic.com` |
| `openai_compatible` | Chat Completions; `max_tokens` | Forced `emit_result` function call | Bearer key to operator-approved HTTPS endpoint |

`emit_result` transports a typed decision/report; it does not execute a business action. Pydantic validates every result locally. The model selects a tool and arguments from scenario-specific contracts inside the Decision. The registry independently validates and authorizes the selected business tool. Provider-side tool formatting is never an authorization mechanism.

Models must support the configured protocol and tool use. No universal model compatibility is claimed. The legacy `JEV_PLANNER=http` path retains JSON-object mode with `JEV_MODEL_ENDPOINT`, `JEV_MODEL` and `JEV_MODEL_KEY`; it uses the same router/accounting layer and can run specialists. Prefer `router` for new deployments.

Protocol references: [OpenAI Chat API](https://developers.openai.com/api/reference/resources/chat) and [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages/create). Supported protocol contracts are covered by local tests; these references do not establish that any live model was tested.

## Routing and fallback

Routes are operator-owned: `default`, `planner:<scenario>`, `supervisor`, `specialist:<role>`, and `judge`. A route specifies one to three distinct model aliases in priority order. Missing specific routes use `default`. Goals and model output cannot supply endpoint URLs, credentials, route definitions or a tenant identity.

A model can retry transient transport failures and HTTP 429/500/502/503/504/529 up to twice. Backoff is bounded exponential, 100 ms then 200 ms. After exhaustion, the next configured provider is tried. Malformed/truncated schema output goes directly to the next configured model. Authentication failures, redirects, refusals, authorization failures and exhausted run budgets are terminal. No write tool is automatically retried.

Fallback sends the same scoped context to another provider. Configure it only where both destinations meet customer data-residency and handling requirements. `openai_compatible` endpoints are trusted operator configuration; restrict outbound traffic at the infrastructure layer. Local HTTP endpoints and redirects are rejected; HTTP proxies inherited from the environment are disabled.

## Budgets and recovery

- Harness: eight planning steps, 35-second execution deadline per invocation, 45-second fenced lease.
- Inference: 24 durable attempts per run, including retries, fallback and parallel specialists. Attempts are reserved in SQLite before network I/O, so restart cannot reset this budget.
- Model requests: configurable 0–2 retries, at most 10 seconds per attempt, 128–4096 output tokens, 48 KB serialized data and 64 KB response cap.
- Tools: three-second read deadline, 25 seconds for LLM release review, at most two argument/read-timeout recovery events per run. All recoveries consume the original step budget.
- API: four concurrent runs per process by default; `JEV_MAX_CONCURRENT_RUNS` accepts 1–32. Overflow returns 429. This is not a distributed limiter.

After invalid arguments, the model observes a sanitized `invalid_tool_arguments` result and may correct its next decision. No rejected input or provider exception body is copied into recovery feedback. Disallowed tools and invalid citations fail immediately. A local write still requires an independent reviewer, exact payload fingerprint, valid expiry and transactional revalidation.

A killed process may reserve an attempt without recording its result. Billing can be unknown after cancellation or connection failure; attempt counts and unknown-usage fields expose that uncertainty. A new lease grants another execution window but does not reset persisted steps or call counts.

## API and Docker

Generate teaching identities before selecting live mode:

```bash
python scripts/dev_credentials.py
set -a; source .env; set +a
python scripts/seed.py
export JEV_PLANNER=router
export JEV_MODELS_CONFIG=config/models.local.json
uvicorn jev_api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Use the authenticated requests in [API.md](API.md). API request bodies cannot override model configuration. Review/resume executes the same planner and retains per-run usage. `/v1/metrics` returns only the authenticated tenant's status and model totals.

For Docker, put the required key environment assignments in your ignored `.env` or inject them using your deployment secret manager. The base Compose file remains fixture-oriented. The explicit live override mounts only the operator's model config read-only:

```bash
docker compose -f compose.yaml -f compose.live.yaml up --build -d --wait
docker compose -f compose.yaml -f compose.live.yaml exec -T api python /app/scripts/seed.py
```

Never commit `.env` or keys. See [production readiness](PRODUCTION_READINESS.md) for identity, persistence, distributed limits and external-tool work that remains.

## Observable inference

Each attempt records provider, configured model, route, prompt name/version/SHA-256, attempt ordinal, outcome, latency, reported input/output tokens and estimated USD cost. The harness saves these as events and run metadata. OpenTelemetry emits child spans plus counters/histograms for calls, tokens, cost and duration. Traces omit raw goals, prompts, answers, key values and exception text.

Set `JEV_OTLP_TRACES_ENDPOINT` and `JEV_OTLP_METRICS_ENDPOINT` to your collector's HTTP `/v1/traces` and `/v1/metrics` endpoints. Use your collector's authentication/TLS configuration outside this teaching reference. Local exporter delivery is tested separately from any hosted collector.

Prices are operator-supplied USD per million tokens, never guessed. Null prices produce null cost. `known_cost_usd` sums only priced attempts; inspect `unpriced_attempts` and `unknown_usage_attempts` alongside it. Calculations are estimates based on reported base input/output tokens; cached-token, reasoning, batch discounts, taxes and provider billing adjustments are not reconciled. Sum-of-call latency includes overlapping specialist calls and is not wall-clock run latency. No hard monetary quota is claimed.

Durable records include goals, evidence and answers; protect the database/backups independently of telemetry redaction.

## Explicit live verification

```bash
JEV_RUN_LIVE_TESTS=1 python scripts/live_smoke.py
jev-eval --live --judge --adversarial --output reports/live-evaluation.json
```

The smoke uses synthetic knowledge data and exits nonzero on a failed run or zero real calls. The manual GitHub workflow requires an explicit billable-call toggle and the `live-provider-validation` environment. Configure `JEV_MODEL_KEY` as an environment secret and endpoint/model as environment variables. Ordinary pull-request CI never receives model credentials or makes paid calls.
