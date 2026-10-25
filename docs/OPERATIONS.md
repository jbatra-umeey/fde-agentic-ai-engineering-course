# Operations runbook

## Supported baseline

One API process, one local SQLite database, bounded workloads and synthetic fixtures. The reference is deliberately easy to operate and inspect. SQLite transactions and lease fencing protect local state; they do not provide a distributed job platform.

## Docker Compose

```bash
python scripts/dev_credentials.py
docker compose up --build -d
docker compose exec api python /app/scripts/seed.py
curl --fail http://127.0.0.1:8000/healthz
docker compose logs --tail=100 api
docker compose down
```

The named volume retains state across `down`/`up`. `docker compose down -v` deletes it; use only when intentionally resetting the synthetic environment. The container runs as a non-root user, drops capabilities, uses a read-only root filesystem and writes only to its data volume and temporary directory.

The container build and Compose runtime must be tested in your own environment if the supplied validation report marks them unexecuted. Add TLS ingress before any remote access. Pin the base-image digest and scan the resulting image in your release pipeline.

## Startup and configuration

| Setting | Meaning |
|---|---|
| `JEV_DB` | Persistent SQLite path; default `var/jev.sqlite` |
| `JEV_IDENTITIES_JSON` | SHA-256 token hashes mapped to tenant/subject/role |
| `JEV_PLANNER` | `fixture` by default, or explicit `http` |
| `JEV_MODEL_ENDPOINT`, `JEV_MODEL`, `JEV_MODEL_KEY` | Optional approved model connection |
| `JEV_OTLP_TRACES_ENDPOINT` | Optional OTLP HTTP trace endpoint, typically ending in `/v1/traces` |
| `OTEL_TRACES_SAMPLER` | Standard OpenTelemetry sampling policy |

Generate fresh high-entropy tokens; do not reuse test strings or commit `.env`. Identity configuration is read on startup, so revoke/rotate by updating the configuration and restarting. For remote use, replace the static-token identity pattern with a reviewed authentication integration.

## Diagnose a failed run

1. Retrieve its state and events using an authorized identity.
2. Check terminal status, error code, step count and last successful tool event.
3. For `run_busy`, inspect whether the original worker is still active. After a process failure, wait for the 45-second lease expiry and resume as the original operator.
4. For `approval_expired`, preserve the historical record and create a fresh reviewed request if still needed.
5. For a failed tool/model call, fix the cause and submit a new request/key. Do not assume a successful HTTP response means task success.
6. Before retrying a future remote action, reconcile the downstream operation ID. The local examples do not solve remote exactly-once delivery.

## Backup and restore

Use SQLite's online backup API rather than copying the live database alone while WAL is active:

```bash
python scripts/maintenance.py backup --db var/jev.sqlite --destination backups/jev.sqlite
```

Store backups securely outside the container host and apply an approved retention policy. To restore, stop writers, preserve the damaged database and its WAL/SHM files, restore the backup to a new database path, point `JEV_DB` to it, run `PRAGMA integrity_check`, and restart. Test read, review and resume with synthetic data before restoring service. Do not overlay a backup onto a live WAL database.

## Retention and capacity

```bash
python scripts/maintenance.py purge --db var/jev.sqlite
```

This purges expired memory and old rate-limit windows. Schedule it in the deployment environment. Run history, document history, effect ledger and backups need a customer-specific retention/deletion policy; they are not automatically removed. Track database/disk size and alert well before exhaustion.

## Proposed pilot signals

Measure time to reviewed task completion, accepted proposal rate, failed runs by code, tool duration, approval waiting age and database disk usage. Establish thresholds with observed customer traffic; the fixture's latency is not a production SLO. Restrict metric access and avoid tenant IDs as unbounded external metric labels.

Spans intentionally omit prompts, raw output and exception bodies. Durable run records still contain goals, evidence and answers; treat the database and backups as sensitive. Review database access and encryption at the infrastructure layer.

## Rollback

Keep the previous application artifact and tested database backup. Stop new work, allow or explicitly interrupt in-flight work, preserve outstanding proposals, roll back the application version and verify schema compatibility. Version 1 rejects an unknown newer schema. Future migrations must document forward/backward compatibility and be tested with production-like data.
