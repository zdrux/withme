#!/usr/bin/env bash
set -euo pipefail

CLUSTER=withme

echo "[1/5] Deleting existing kind cluster (if any)..."
kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true

echo "[2/5] Creating kind cluster with host port mappings (80/443)..."
kind create cluster --config infra/kind/kind-withme.yaml

echo "[3/5] Installing ingress-nginx (kind provider)..."
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11.1/deploy/static/provider/kind/deploy.yaml
kubectl -n ingress-nginx rollout status deploy/ingress-nginx-controller --timeout=300s

echo "[4/5] Ensuring hosts entry..."
if ! grep -q 'api.withme.local' /etc/hosts; then
  echo '127.0.0.1 api.withme.local' | sudo tee -a /etc/hosts >/dev/null
fi

echo "[5/5] Deploying app stack..."
scripts/dev_deploy_kind.sh

echo "Done. Try: curl http://api.withme.local/health"

