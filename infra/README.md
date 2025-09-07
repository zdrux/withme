With Me — Infra Guide

Overview
- Kubernetes manifests live in `infra/k8s/`. A local kind cluster config is in `infra/kind/kind-withme.yaml`.

Images
- Build:
  - API: `docker build -f api/Dockerfile -t ghcr.io/<org-or-user>/withme-api:0.1.0 .`
  - Worker: `docker build -f worker/Dockerfile -t ghcr.io/<org-or-user>/withme-worker:0.1.0 .`
- Push (after `docker login ghcr.io`):
  - `docker push ghcr.io/<org-or-user>/withme-api:0.1.0`
  - `docker push ghcr.io/<org-or-user>/withme-worker:0.1.0`

Cluster Setup
- Namespace: `kubectl create namespace withme` (optional, update manifests if omitted).
- Secrets:
  - From `.env`: `kubectl -n withme create secret generic withme-secrets --from-env-file=.env`
  - Or edit/apply: `infra/k8s/secrets-template.yaml` with base64 values.

Apply Manifests
- `kubectl -n withme apply -f infra/k8s/redis.yaml`
- `kubectl -n withme apply -f infra/k8s/api-deployment.yaml`
- `kubectl -n withme apply -f infra/k8s/worker-deployment.yaml`
- `kubectl -n withme apply -f infra/k8s/cronjobs.yaml` (optional)
- `kubectl -n withme apply -f infra/k8s/ingress.yaml` (optional)

Migrations
- `infra/k8s/migrate-job.yaml` runs Alembic. Ensure the job image matches the API image that contains the code and Alembic config.
  - Run: `kubectl -n withme apply -f infra/k8s/migrate-job.yaml`

Local (kind)
- Create: `kind create cluster --config infra/kind/kind-withme.yaml`
- Map: exposes host 80/443 to cluster ingress.

Notes
- Health/readiness: `/health` on port 8080.
- Cron security token: ensure `CRON_TOKEN` in `withme-secrets`.
- Do not commit secrets; use secrets templates and secure channels.

