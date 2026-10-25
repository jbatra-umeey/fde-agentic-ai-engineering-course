# Verification report

Final review date: 25 October 2026 (Asia/Kolkata). Python 3.12.14, Linux.

## Executed checks

| Check | Result | Evidence |
|---|---|---|
| Automated test suite | 53 passed; 0 failed | `tests.txt`, `tests.xml` |
| Coverage across core, API, tools, workflows and evals | 92% rounded statement coverage | `coverage.json` |
| Ten focused lessons | All ten executed by parametrized tests | `tests/test_lessons.py` |
| Integrated evaluation | 5/5 scenarios passed all defined checks | `evaluation.json` |
| Lint and formatting | Ruff checks passed | Reproducible commands in README |
| Dependency consistency | `pip check` passed | Installed dependency constraints |
| Package build | Wheel and source distribution built successfully | `build.txt` |
| Installed-wheel smoke | All five scenarios succeeded from the installed wheel | `package-smoke.json` |
| Real localhost HTTP API | Startup, create, independent review and anonymous denial passed | `package-smoke.json` |
| SQLite online backup | Backup completed and integrity check passed | `package-smoke.json` |
| Diagram syntax | 14 Mermaid blocks parsed successfully | `diagrams.json` |

The test suite includes cross-tenant denial, invalid tool arguments, exact approval binding, self-review rejection, review expiry, concurrent duplicate approval, invoice revalidation, duplicate refunds, idempotency conflict, lease fencing, interruption recovery, iteration limits, timeout, citation validation, memory isolation/expiry/deletion, parallel cancellation, provider retry/response contracts, and telemetry metadata redaction.

The coverage figure excludes CLI scripts and does not imply every production failure mode is covered. The five evaluation cases are synthetic and deterministic. The live-model adapter was tested through mock HTTP transport, not a real hosted model.

## Warning and unexecuted work

- One dependency deprecation warning: the installed Starlette TestClient warns about its HTTPX integration. Tests pass; track the dependency's migration guidance before the next upgrade.
- Docker build, Compose startup, seeding and the API health check passed in [GitHub Actions run 40166920728](https://github.com/jbatra-umeey/fde-agentic-ai-engineering-course/actions/runs/40166920728) on commit `c626d82`. Image vulnerability scanning was not performed.
- The published baseline passed hosted CI. Subsequent run results are available in the repository Actions tab.
- External business-system integrations, actual model-provider compatibility, production load/SLOs, vulnerability auditing, penetration testing and collector/backend delivery were not tested.
- Mermaid syntax was parsed. Ten PNG/SVG illustrations were rendered and visually reviewed; the SVG sources contain no footer labels.

An initial tracing walkthrough failed because environment sampling omitted spans. The in-memory teaching/test exporter now uses explicit always-on sampling; the final suite passes. Production exporter sampling continues to use standard OpenTelemetry configuration.

## Reproduce

Use the pinned dependency setup in README, then run the check/test/eval/build commands. Keep your own report with environment, commit or source checksum, actual results and deployment-specific gaps. Do not reuse this report as evidence for a changed artifact or customer environment.
