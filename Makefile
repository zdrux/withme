PYTHON ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PY := $(VENV)/bin/python

.PHONY: venv install dev test lint format type worker

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

