# Repository Guidelines

## Project Structure & Module Organization
- `docs/`: Product and design docs (see `docs/INSTRUCTIONS.MD`).
- `api/`: FastAPI service (app code in `api/withme/`, routers in `api/withme/routes/`, schemas in `api/withme/schemas/`).
- `worker/`: Background jobs for images, events, semantic refresh.
- `web/`: Simple web test UI.
- `mobile/`: Flutter app (primary client).
- `infra/`: Kubernetes manifests and ops scripts.

Note: Some folders may be introduced as code lands; keep this layout when adding components.

## Build, Test, and Development Commands
- Backend dev: `uvicorn api.main:app --reload` — run API locally.
- Tests: `pytest -q` — run unit/integration tests.
- Lint/format: `ruff check .` and `black .` — static checks and formatting.
- Type check: `mypy api worker` — optional but encouraged for PRs touching logic.
- Web UI: `npm install && npm run dev` in `web/` — local web tester.
- Flutter: `flutter run` in `mobile/` — launch the app on a device/simulator.

## Coding Style & Naming Conventions
- Python 3.11+, 4‑space indent; modules/functions `snake_case`, classes `PascalCase`.
- API: routers in `api/withme/routes/*.py`; Pydantic models in `api/withme/schemas/*.py`.
- JSON and DB fields use `snake_case` (aligns with the DDL in the PRD).
- Tools: `black` (line length 88), `ruff` (incl. import sorting), `mypy` for critical modules.
- Keep files small and cohesive; prefer `services/` and `repositories/` layers over fat routers.

## Testing Guidelines
- Framework: `pytest` with `httpx`/FastAPI `TestClient` for API tests.
- Layout: `api/tests/` and `worker/tests/`; name tests `test_*.py`.
- Aim for ≥80% coverage on core logic (affinity, mood, scheduling, retrieval).
- Example: `pytest -k affinity` to target a subset while iterating.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- Keep PRs focused; include:
  - Clear description and rationale; link relevant sections of `docs/INSTRUCTIONS.MD`.
  - Screenshots/GIFs for UI changes; sample requests/responses for API changes.
  - Schema changes: include migration notes and rollout plan.
- Pass lint/tests locally before requesting review.

## Security & Configuration Tips
- Never commit secrets. Use `.env` locally and Kubernetes `Secret` in `infra/`.
- Common env vars: `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `PINECONE_API_KEY`, `REDIS_URL`, `FAL_API_KEY`, `FCM_SERVER_KEY`.
- Log responsibly: avoid PII; mask tokens; keep structured logs with request IDs.

