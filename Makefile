PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python

.PHONY: venv install dev test lint format type worker \
        docker-build docker-build-api docker-build-worker \
        k8s-namespace k8s-secrets-from-env k8s-apply k8s-apply-core \
        k8s-apply-ingress k8s-apply-cron k8s-migrate \
        k8s-scale-zero k8s-delete-cron kind-up

venv:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip

install: venv
	$(PIP) install -r requirements.txt

dev:
	$(VENV)/bin/uvicorn api.main:app --reload --port 8080

test:
	$(VENV)/bin/pytest -q

lint:
	$(VENV)/bin/ruff check .

format:
	$(VENV)/bin/black .

type:
	$(VENV)/bin/mypy api worker || true

worker:
	$(PY) -m worker.run

# --- Docker ---
IMAGE_PREFIX ?= ghcr.io/withme
API_IMAGE ?= $(IMAGE_PREFIX)/api:0.1.0
WORKER_IMAGE ?= $(IMAGE_PREFIX)/worker:0.1.0

docker-build: docker-build-api docker-build-worker ## Build both images

docker-build-api:
	docker build -f api/Dockerfile -t $(API_IMAGE) .

docker-build-worker:
	docker build -f worker/Dockerfile -t $(WORKER_IMAGE) .

# --- Kubernetes ---
KNS ?= withme

k8s-namespace:
	kubectl get ns $(KNS) >/dev/null 2>&1 || kubectl create namespace $(KNS)

k8s-secrets-from-env: ## Create/update secret from .env
	kubectl -n $(KNS) create secret generic withme-secrets \
	  --from-env-file=.env --dry-run=client -o yaml | kubectl apply -f -

k8s-apply-core: k8s-namespace ## Apply core services (redis, api, worker)
	kubectl -n $(KNS) apply -f infra/k8s/redis.yaml
	kubectl -n $(KNS) apply -f infra/k8s/api-deployment.yaml
	kubectl -n $(KNS) apply -f infra/k8s/worker-deployment.yaml

k8s-apply-ingress:
	kubectl -n $(KNS) apply -f infra/k8s/ingress.yaml

k8s-apply-cron:
	kubectl -n $(KNS) apply -f infra/k8s/cronjobs.yaml

k8s-apply: k8s-apply-core k8s-apply-cron ## Apply all default manifests

k8s-migrate: ## Run the migrate job (ensure image matches your API build)
	kubectl -n $(KNS) apply -f infra/k8s/migrate-job.yaml

k8s-scale-zero: ## Scale down API and worker
	kubectl -n $(KNS) scale deploy/api --replicas=0 || true
	kubectl -n $(KNS) scale deploy/worker --replicas=0 || true

k8s-delete-cron: ## Delete cronjobs
	kubectl -n $(KNS) delete cronjob/daily-event cronjob/semantic-refresh || true

kind-up:
	kind create cluster --config infra/kind/kind-withme.yaml
