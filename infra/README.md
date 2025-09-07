With Me — Infra Guide

Overview
- Kubernetes manifests live in `infra/k8s/`. A local kind cluster config is in `infra/kind/kind-withme.yaml`.

Images
- Build:
  - `make docker-build` (or build individually):
  - API: `docker build -f api/Dockerfile -t ghcr.io/<org-or-user>/withme-api:0.1.0 .`
  - Worker: `docker build -f worker/Dockerfile -t ghcr.io/<org-or-user>/withme-worker:0.1.0 .`

Cluster Setup
- Namespace: `kubectl create namespace withme` (optional, update manifests if omitted).
- Secrets:
  - From `.env`: `kubectl -n withme create secret generic withme-secrets --from-env-file=.env`
  - Or edit/apply: `infra/k8s/secrets-template.yaml` with base64 values.

Apply Manifests (Supabase DB)
- One-command apply (recommended):
  - `make k8s-all` (creates namespace, secret from `.env`, and applies all k8s resources via kustomize)
- Or manual:
  - `make k8s-namespace`
  - `make k8s-secrets-from-env`
  - `kubectl -n withme apply -k infra/k8s`
Note: Use Supabase as Postgres. Ensure `DATABASE_URL` is set in secret `withme-secrets`. The `postgres.yaml` is an example only and not required for managed DB.

Migrations
- `infra/k8s/migrate-job.yaml` runs Alembic. Ensure the job image matches the API image that contains the code and Alembic config.
  - Run: `kubectl -n withme apply -f infra/k8s/migrate-job.yaml`

Local (kind)
- Create: `kind create cluster --config infra/kind/kind-withme.yaml`
- Map: exposes host 80/443 to cluster ingress.

Notes
- Health/readiness: `/health` on port 8080.
- Cron security token: ensure `CRON_TOKEN` in `withme-secrets`.
- In this archival snapshot, `.env` is committed; you can run `make k8s-secrets-from-env` to create the cluster secret. For ongoing ops, do not commit secrets.
