# Upgrade verification report

Date: 25 October 2026 (Asia/Kolkata). Python 3.12.14, Linux. Version 0.2.0.
Inspected starting commit: `b752521ae550aa1d4d7547fc95172fb2454dcc73`.
The supplied live-inference ZIP overlay was inspected/applied, then extended with the provider, specialist, evaluation and telemetry implementation.

## Executed checks on this upgrade

| Check | Verified result | Evidence |
|---|---|---|
| Automated tests | 97 passed, 0 failed | [tests.txt](tests.txt), [JUnit XML](tests.xml) |
| Coverage: core, API, tools, workflows, evals | 93.39% statement coverage; required threshold 85% | [coverage.json](coverage.json) |
| Lint, formatting and Python compilation | Passed | Ruff check/format, compileall |
| Golden regression evaluation | 5/5 passed | [evaluation.json](evaluation.json) |
| Golden plus injection evaluation | 8/8 passed; baseline comparison passed | [adversarial-evaluation.json](adversarial-evaluation.json) |
| Package build | Wheel and source distribution built | [build.txt](build.txt) |
| Clean installed-wheel smoke | Four packaged prompts, ten lessons and eight evaluations passed outside source tree | [package-smoke.json](package-smoke.json) |
| Real localhost HTTP API | Startup, health, auth denial, self-review denial and independent review passed | [http-smoke.json](http-smoke.json) |
| Local OTLP HTTP delivery | Real trace/metric HTTP exports decoded and checked | `tests/test_otlp_export.py` |
| Documentation links and basic credential-pattern scan | Passed | `scripts/check_repository.py` |
| Mermaid syntax | 19 diagrams parsed with Mermaid | [diagrams.json](diagrams.json) |
| Original course preservation | 49 original teaching/example/illustration files retained; illustration bytes unchanged | [preservation.json](preservation.json) |
| Dependency consistency | `pip check` passed | Pinned requirements installed |
| Workflow and Compose YAML syntax | All three workflows and two Compose files parsed | YAML parser |

Provider contract tests cover both native HTTP protocols, legacy JSON mode, model routing/fallback, retries, schema failures, refusal/auth/redirect failure policy, deadlines, per-run concurrent accounting, cost arithmetic and redaction. Integration tests connect the actual HTTP planner to API/CLI/lessons, supervisor/specialists and judge with controlled HTTP transports. Tests also cover bounded argument/read-timeout recovery, denied injected actions, invalid specialist citations, API concurrency rejection and authoritative release-review requirements.

## Unverified external functionality and limitations

- No OpenAI, Anthropic or legacy model credentials were configured. No live model request, semantic-quality result or judge calibration is claimed. Controlled transports test contracts, not real-provider compatibility.
- Docker is unavailable in the local execution environment. Docker build, Compose startup/seeding and container health are configured in PR CI; consult the PR checks for this exact commit. Earlier baseline CI is not evidence for this upgrade.
- The release workflow is defined and YAML-parsed but has not published an image or deployed an environment. The manual billable-provider workflow has not run.
- Local OTLP exporter delivery passed; delivery to a hosted collector/backend, dashboards and alerting remain untested.
- Real Jira/payment/source connectors, OIDC, distributed quotas/persistence, production load/SLOs, penetration testing and vulnerability-policy enforcement remain deployment work.
- Cost is a base-token estimate from operator-configured rates. Missing usage/prices remain unknown; provider invoice reconciliation and hard monetary quotas are not implemented.
- Golden and injection cases are synthetic. Fixture success and contract tests do not establish prompt-injection immunity, real-model quality or factual entailment.
- One upstream TestClient deprecation warning remains: Starlette warns about its HTTPX integration. All tests pass.

## Reproduce

Follow the pinned setup in README, then run `make check test eval`, `jev-eval --adversarial`, `python -m build`, `python scripts/http_smoke.py`, and the installed-wheel smoke described in CI. Use `python scripts/check_course_preservation.py --base b752521 --output reports/preservation.json` to audit original material. Enable live integration only with configured credentials and explicit opt-in. See [readiness gaps](../docs/PRODUCTION_READINESS.md).
