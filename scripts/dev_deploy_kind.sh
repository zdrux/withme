#!/usr/bin/env bash
set -euo pipefail

NS=withme
CLUSTER=withme

# Load local env if present
set +u
if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | xargs -d '\n' -I{} echo {})
fi
set -u

echo "[1/9] Building images..."
docker build -t withme-api:dev -f api/Dockerfile .
docker build -t withme-worker:dev -f worker/Dockerfile .

echo "[2/9] Loading images into kind..."
kind load docker-image withme-api:dev --name "$CLUSTER"
kind load docker-image withme-worker:dev --name "$CLUSTER"

echo "[3/9] Ensuring namespace and secrets..."
kubectl get ns "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"
kubectl -n "$NS" create secret generic withme-secrets \
  --from-literal=ENVIRONMENT=dev \
  --from-literal=REDIS_URL=redis://redis.$NS.svc.cluster.local:6379/0 \
  --from-literal=DATABASE_URL=${DATABASE_URL:-postgresql+asyncpg://withme:withme@postgres.$NS.svc.cluster.local:5432/withme} \
  --from-literal=SUPABASE_URL=${SUPABASE_URL:-} \
  --from-literal=SUPABASE_PROJECT_URL=${SUPABASE_PROJECT_URL:-} \
  --from-literal=SUPABASE_DB_PASSWORD=${SUPABASE_DB_PASSWORD:-} \
  --from-literal=SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY:-} \
  --from-literal=SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY:-} \
  --from-literal=SUPABASE_JWT_SECRET=${SUPABASE_JWT_SECRET:-} \
  --from-literal=SUPABASE_JWT_TOKEN=${SUPABASE_JWT_TOKEN:-} \
  --from-literal=OPENAI_API_KEY=${OPENAI_API_KEY:-} \
  --from-literal=PINECONE_API_KEY=${PINECONE_API_KEY:-} \
  --from-literal=PINE_CONE_API_KEY=${PINE_CONE_API_KEY:-} \
  --from-literal=FAL_API_KEY=${FAL_API_KEY:-} \
  --from-literal=FALAI_API_KEY=${FALAI_API_KEY:-} \
  --from-literal=CRON_TOKEN=${CRON_TOKEN:-changeme} \
  --dry-run=client -o yaml | kubectl apply -f -

echo "[4/9] Applying DB and Redis..."
kubectl -n "$NS" apply -f infra/k8s/postgres.yaml
kubectl -n "$NS" apply -f infra/k8s/redis.yaml

echo "[5/9] Waiting for Postgres..."
kubectl -n "$NS" rollout status deploy/postgres --timeout=240s

echo "[6/9] Running DB migrations..."
kubectl -n "$NS" delete job migrate --ignore-not-found
kubectl -n "$NS" apply -f infra/k8s/migrate-job.yaml
kubectl -n "$NS" wait --for=condition=complete job/migrate --timeout=240s

echo "[7/9] Deploying API and worker..."
kubectl -n "$NS" apply -f infra/k8s/api-deployment.yaml
kubectl -n "$NS" apply -f infra/k8s/worker-deployment.yaml

echo "[8/9] Setting dev images..."
kubectl -n "$NS" set image deploy/api api=withme-api:dev
kubectl -n "$NS" set image deploy/worker worker=withme-worker:dev || true

echo "[9/9] Waiting for rollouts..."
kubectl -n "$NS" rollout status deploy/redis --timeout=180s
kubectl -n "$NS" rollout status deploy/api --timeout=180s
kubectl -n "$NS" rollout status deploy/worker --timeout=180s || true

echo "[Done] Services:"
kubectl -n "$NS" get svc

echo "Applying ingress..."
kubectl -n "$NS" apply -f infra/k8s/ingress.yaml
echo "Tip: add to /etc/hosts: 127.0.0.1 api.withme.local, then open http://api.withme.local"
