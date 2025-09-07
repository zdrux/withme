With Me — Project Wind‑Down Summary

Last updated: 2025-09-07

Scope
- FastAPI API service (`api/`), background worker (`worker/`), simple web test UI (`web/`), and Kubernetes manifests (`infra/`).
- Data/backends: Supabase Postgres, Redis, Pinecone, OpenAI, Fal.AI, FCM.

Repository State
- Branch: `master`.
- Working tree: clean at time of this commit (no uncommitted changes).
- `.env` remains uncommitted per security policy; `.env.example` provided.

Build Artifacts
- Dockerfiles: `api/Dockerfile`, `worker/Dockerfile`.
- Python deps: `requirements.txt`. Local tooling via `Makefile` and `.venv` recommended.

Container Build & Push
- Login (GHCR example):
  - `echo $GHCR_TOKEN | docker login ghcr.io -u $GITHUB_USER --password-stdin`
- Build tags:
  - API: `docker build -f api/Dockerfile -t ghcr.io/<org-or-user>/withme-api:0.1.0 .`
  - Worker: `docker build -f worker/Dockerfile -t ghcr.io/<org-or-user>/withme-worker:0.1.0 .`
- Push:
  - `docker push ghcr.io/<org-or-user>/withme-api:0.1.0`
  - `docker push ghcr.io/<org-or-user>/withme-worker:0.1.0`

Kubernetes Deployment
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
- Do NOT commit `.env` or raw API keys. Use Kubernetes Secrets or a secret manager. An example `secrets-template.yaml` is included.
- For handoff, provide encrypted delivery of actual secrets (out-of-band).

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

