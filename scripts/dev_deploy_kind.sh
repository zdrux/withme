#!/usr/bin/env bash
set -euo pipefail

NS=withme
CLUSTER=withme

echo "[1/6] Building images..."
docker build -t withme-api:dev -f api/Dockerfile .
docker build -t withme-worker:dev -f worker/Dockerfile .

echo "[2/6] Loading images into kind..."
kind load docker-image withme-api:dev --name "$CLUSTER"
kind load docker-image withme-worker:dev --name "$CLUSTER"

echo "[3/6] Ensuring namespace and secrets..."
kubectl get ns "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"
kubectl -n "$NS" create secret generic withme-secrets \
  --from-literal=ENVIRONMENT=dev \
  --from-literal=REDIS_URL=redis://redis.$NS.svc.cluster.local:6379/0 \
  --dry-run=client -o yaml | kubectl apply -f -

echo "[4/6] Applying manifests..."
kubectl -n "$NS" apply -f infra/k8s/redis.yaml
kubectl -n "$NS" apply -f infra/k8s/api-deployment.yaml
kubectl -n "$NS" apply -f infra/k8s/worker-deployment.yaml

echo "[5/6] Setting dev images..."
kubectl -n "$NS" set image deploy/api api=withme-api:dev
kubectl -n "$NS" set image deploy/worker worker=withme-worker:dev || true

echo "[6/6] Waiting for rollouts..."
kubectl -n "$NS" rollout status deploy/redis --timeout=180s
kubectl -n "$NS" rollout status deploy/api --timeout=180s
kubectl -n "$NS" rollout status deploy/worker --timeout=180s || true

echo "[Done] Services:"
kubectl -n "$NS" get svc

echo "Tip: port-forward API: kubectl -n $NS port-forward svc/api 8090:80"

