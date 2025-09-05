# With Me — Build Progress and Next Steps

## Today’s Outcome
- API: FastAPI app with chat, messages, agent, state, image jobs, admin, cron, health/status.
- Persistence: Postgres + Alembic models; messages, agents, devices, events, semantic memory, image jobs.
- Worker: RQ + Redis; Fal.AI (flux-pro v1.1-ultra) image generation with polling/fallback.
- Intelligence: OpenAI replies (persona + mood + availability + scenarios + semantic hints); basic mood/affinity updates per turn.
- Retrieval: Pinecone scaffolding + semantic query hooks; accepts `PINECONE_API_KEY` or `PINE_CONE_API_KEY`.
- Infra: kind cluster with NGINX Ingress (host-level 80/443). Ingress hosts: `withme.apps.redkube.io`, `api.withme.local`.
- Web UI: Chat at `/web` with correct scroll (newest at bottom), load earlier, image request, token field.

## How to Use
- Open UI: http://withme.apps.redkube.io/ (token: `dev` in this phase).
- Key endpoints: `/chat/send`, `/messages`, `/chat/request_image`, `/agent`, `/state`, `/status`.
- Secrets: managed via `withme-secrets` (OpenAI, Fal.AI, Supabase, Pinecone, `CRON_TOKEN`).

## Known Gaps / Open Items
- Auth: Supabase JWT verification exists server-side; UI login not implemented (use `dev`).
- Retrieval: Need real semantic_memory summaries + Pinecone metadata/indexing.
- Offline life: Cron handlers are basic; enrich events and mood baseline.
- Prompt contract: Expand to reflect affinity gates and richer tone guidance.
- Observability: Add request IDs, structured logs, simple rate limit.
- UI: Typing indicator, nicer timestamps, error toasts.

## Next Steps (Suggested)
1) Persist semantic_memory from convo; index into Pinecone (with metadata).
2) Enrich prompt (affinity-gated warmth, image thresholds, scenario arcs).
3) Improve daily_event + semantic_refresh; schedule initiations.
4) UI polish (typing, time format, toasts) and minimal admin view.

## Operational Notes
- Recreate cluster with host ports: `scripts/recreate_kind_with_ingress.sh`.
- Deploy/update to kind: `scripts/dev_deploy_kind.sh`.
- Quick rollouts: rebuild images, `kind load ...`, `kubectl set image`, `rollout status`.
- UI path: `/` → `/web` (static served by API).

