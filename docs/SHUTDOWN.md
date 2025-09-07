With Me — Project Wind‑Down Summary

Last updated: 2025-09-07

Scope
- FastAPI API service (`api/`), background worker (`worker/`), simple web test UI (`web/`), and Kubernetes manifests (`infra/`).
- Data/backends: Supabase Postgres, Redis, Pinecone, OpenAI, Fal.AI, FCM.

Repository State
- Branch: `master`.
- Working tree: clean at time of this commit (no uncommitted changes).
- `.env` is included in this repo per wind‑down request for archival and reproducibility; `.env.example` remains for reference.

Build Artifacts
- Dockerfiles: `api/Dockerfile`, `worker/Dockerfile`.
- Python deps: `requirements.txt`. Local tooling via `Makefile` and `.venv` recommended.

Container Build
- Use Makefile targets or raw docker commands:
  - `make docker-build` (builds both API and Worker)
  - API only: `docker build -f api/Dockerfile -t ghcr.io/<org-or-user>/withme-api:0.1.0 .`
  - Worker only: `docker build -f worker/Dockerfile -t ghcr.io/<org-or-user>/withme-worker:0.1.0 .`

Kubernetes Deployment (Supabase DB)
- Manifests under `infra/k8s/`:
  - `api-deployment.yaml`, `worker-deployment.yaml`, `redis.yaml`, `ingress.yaml` (optional), `cronjobs.yaml`, `migrate-job.yaml`, `postgres.yaml` (example), `secrets-template.yaml`.
- Namespace (optional): `kubectl create namespace withme`
- Secrets:
  - Prefer generating from local env: `kubectl -n withme create secret generic withme-secrets --from-env-file=.env --dry-run=client -o yaml > infra/k8s/secrets.yaml`
  - Or edit `infra/k8s/secrets-template.yaml` with base64 values and apply.
- Apply core services:
  - `kubectl -n withme apply -f infra/k8s/redis.yaml`
  - `kubectl -n withme apply -f infra/k8s/api-deployment.yaml`
  - `kubectl -n withme apply -f infra/k8s/worker-deployment.yaml`
  - Optional ingress: `kubectl -n withme apply -f infra/k8s/ingress.yaml`
  - CronJobs: `kubectl -n withme apply -f infra/k8s/cronjobs.yaml`
- Database:
  - Use Supabase managed Postgres. Ensure `DATABASE_URL` in `withme-secrets` points to Supabase.
- DB migrations:
  - Edit `infra/k8s/migrate-job.yaml` image to match your built API image if needed, then: `kubectl -n withme apply -f infra/k8s/migrate-job.yaml`

Local Cluster (kind)
- `infra/kind/kind-withme.yaml` exposes ports 80/443 and labels control-plane for ingress.
- Create cluster: `kind create cluster --config infra/kind/kind-withme.yaml`

Operational Notes
- Health endpoint: `GET /health` used for liveness/readiness.
- Cron security: `CRON_TOKEN` required by cronjobs; include in the `withme-secrets` secret.
- Observability: use structured logs with request IDs; avoid logging PII; rate limits should be configured in API.

Security & Secrets
- This repository intentionally commits `.env` and API keys as part of the wind‑down to preserve a complete snapshot. Treat this repo as highly sensitive and private.
- For ongoing operation, rotate all keys, and avoid committing secrets. Use Kubernetes Secrets or a secret manager. `infra/k8s/secrets-template.yaml` is included.

Decommission Checklist
- Disable cronjobs: `kubectl -n withme delete cronjob/daily-event cronjob/semantic-refresh`.
- Scale workloads to zero: `kubectl -n withme scale deploy/api --replicas=0 && kubectl -n withme scale deploy/worker --replicas=0`.
- Revoke API keys at providers (OpenAI, Pinecone, Fal.AI, FCM, Supabase).
- Archive GH repo and container images if desired.

Next Owners Quickstart
- Dev server: `uvicorn api.main:app --reload`.
- Tests: `pytest -q`; Lint/format: `ruff check .`, `black .`.
- Type checks: `mypy api worker`.

Contact & Handoff
- See `docs/INSTRUCTIONS.MD` for the full PRD, API outline, and deployment details.
