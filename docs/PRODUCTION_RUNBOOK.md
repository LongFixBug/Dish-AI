# FoodAI production runbook

## Required configuration

- Set `ENVIRONMENT=production` and a unique `AUTH_SECRET_KEY` of at least 32 characters.
- Use a non-development `DATABASE_URL`; PostgreSQL, Redis and Qdrant must stay on a private network.
- Set `RATE_LIMIT_BACKEND=redis` and `REDIS_URL` to the private Redis service.
- Set `OBJECT_STORAGE_BACKEND=s3`, configure `S3_BUCKET`, and enable bucket versioning, server-side encryption and lifecycle retention.
- Set `CV_ENABLED=false` for the API-only image, or deploy a separate image that packages Torch and the approved checkpoint.
- If `VISION_ENABLED=true`, set `VISION_API_KEY`. `/ready` remains red when an enabled capability is unavailable.
- Never copy placeholder values from `.env.example`; production startup rejects placeholder auth, Vision, metrics and database credentials.
- Enable `TRUST_PROXY_HEADERS` only when the ingress strips client-supplied forwarding headers and writes its own trusted value.

## Deploy

1. Run `docker run --rm --env-file <production-env> <api-image> alembic upgrade head` as a one-off migration job.
2. Start the new API revision without routing traffic to it.
3. Wait for `/live` to return 200 and `/ready` to return 200.
4. Route a small canary percentage, check latency/error/cost metrics, then continue rollout.
5. Roll back application traffic immediately if readiness, error rate or model quality gates fail. Do not downgrade the database automatically.

## Mobile release

- Configure GitHub secrets `API_BASE_URL` (HTTPS only), `ANDROID_KEY_PROPERTIES` and base64-encoded `ANDROID_UPLOAD_KEYSTORE`.
- Push a `mobile-v*` tag only after CI passes; the release workflow analyzes, tests and creates a signed Android App Bundle.
- Keep debug cleartext networking confined to the Android debug manifest. Release builds fail fast without an HTTPS API endpoint.

## PostgreSQL backup and restore

- Run `scripts/backup_postgres.sh` from a trusted backup runner with `POSTGRES_BACKUP_URL` set through the secret manager.
- Store the resulting custom-format dump outside the application host. Encrypt it and apply an immutable retention policy.
- Production should also enable provider-managed PITR/WAL archival; logical dumps are the second recovery layer.
- Once per month, restore the newest backup into an isolated database using `scripts/restore_postgres.sh`, run `alembic current`, catalog audit and API smoke tests, then record recovery time and data-loss window.
- Restore requires `FOODAI_RESTORE_CONFIRM=restore-foodai` to reduce accidental destructive runs.

## Object storage

- Feedback objects enter with metadata status `pending`; they must not be copied into a training split before human approval.
- Keep public access disabled. API credentials need only `PutObject`, `DeleteObject`, `GetObject` and bucket health permissions for the configured prefix.
- Apply lifecycle deletion aligned with `FEEDBACK_RETENTION_DAYS` and verify that database metadata and object lifecycle reports agree.
- Schedule `scripts/purge_expired_feedback.py` and `scripts/purge_expired_refresh_tokens.py` daily from a trusted maintenance runner.

## Model release

- Evaluate an independent test split with `python ml/evaluation/cv_release.py`; validation metrics alone cannot promote a checkpoint.
- Promote only a manifest that passes every gate with `python scripts/promote_model.py promote --manifest <path>`.
- Build `Dockerfile.cv` only after `checkpoints/best_model.manifest.json` exists and its checksum matches the approved checkpoint.
- Roll back atomically with `python scripts/promote_model.py rollback` when live quality or latency breaches the release threshold.

## Incident checks

- Authentication incident: rotate `AUTH_SECRET_KEY`, revoke refresh tokens, and force mobile sign-in again.
- Vision cost spike: disable `VISION_ENABLED` or reduce analyze quota, then inspect per-user/request metrics.
- Qdrant loss: keep PostgreSQL online, rebuild the derived index with `scripts/reindex_qdrant.py` and verify UUID drift.
- Database incident: stop writes, select PITR or tested dump recovery, restore to a new instance, run integrity checks, then switch traffic.
