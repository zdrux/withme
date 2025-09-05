# With Me — Build Progress and Next Steps

## Today’s Outcome
- API: FastAPI app with chat, messages, agent, state, image jobs, admin panel (agents/scenarios/events), cron, health/status.
- Persistence: Postgres + Alembic; tables for users, agents, messages, events, semantic_memory, image_jobs, affinity_deltas (new: agents.timezone, agents.base_image_url; image_jobs.kind).
- Worker: RQ + Redis; Fal.AI integration (Flux for base portraits, nano-banana/edit for variations) with robust submit/poll logging and Supabase upload; falls back to placeholder only if Fal unavailable.
- Intelligence: OpenAI replies using persona + mood + availability + scenarios + semantic hints; basic mood/affinity updates per turn; identity/time-awareness in prompts (home_city, occupation, timezone, local time, small weather flavor); self-reference guard.
- Retrieval: Pinecone scaffolding + semantic query hooks; embeddings for messages + semantic memory (best-effort).
- Infra: kind cluster with NGINX Ingress (host-level 80/443). Ingress hosts: `withme.apps.redkube.io`, `api.withme.local`.
- Web UI: Chat at `/web` (agent selector, newest at bottom, load earlier). The image request input was removed — ask the agent for a pic in text. Admin panel at `/web/admin.html` (create/generate with appearance prompt, edit persona/identity/timezone, view scenarios/events, preview base image).

## How to Use
- Open UI: http://withme.apps.redkube.io/ (token: `dev` in this phase).
- Admin: `/web/admin.html` → Create or Generate an agent (optionally provide Appearance Prompt). On create/generate, a base portrait job is queued (Flux) and stored in Supabase.
- Chat: `/web/` → select agent from dropdown → ask for a “selfie/photo/picture”. If gating allows, an edit job is queued (nano-banana/edit) using the base portrait.
- Key endpoints: `/chat/send`, `/messages`, `/agent`, `/state`, `/status` (programmatic: `/chat/request_image` remains but UI avoids it).
- Secrets: managed via `withme-secrets` (OpenAI, Fal.AI via `FAL_API_KEY`, Supabase, Pinecone, `CRON_TOKEN`).

## Known Gaps / Open Items
- Auth: Supabase JWT verification exists server-side; UI login not implemented (use `dev`).
- Retrieval: Need real semantic_memory summaries + Pinecone metadata/indexing.
- Offline life: Cron handlers are basic; enrich events and mood baseline.
- Prompt contract: Continue tuning for identity, tone, gating, scenarios.
- Observability: Add request IDs, structured logs, simple rate limit.
- UI: Typing indicator, nicer timestamps, error toasts; optional Admin “Regenerate Base Image”.

## Next Steps (Suggested)
1) Switch Fal to webhook flow (attach `webhook_url` on submit) and use polling as a fallback only.
2) Show base portrait thumbnails in Admin list/chat header; add “Regenerate Base Image” action.
3) Retrieval polish: embed more recent messages with metadata; union recency + semantic; de-dup.
4) Initiations scheduler: compute per §7.3; enforce caps; send via FCM.
5) UI polish: typing, toasts, timestamps; job status surface (queued/running/succeeded/failed).

## Operational Notes
- Recreate cluster with host ports: `scripts/recreate_kind_with_ingress.sh`.
- Deploy/update to kind: `scripts/dev_deploy_kind.sh`.
- Quick rollouts: rebuild images, `kind load ...`, `kubectl set image`, `rollout status`.
- UI path: `/` → `/web` (static served by API).
- Fal keys: set `FAL_API_KEY` in `withme-secrets` (alias `FALAI_API_KEY` is supported but `FAL_API_KEY` preferred now).
- Supabase Storage: ensure bucket `agent-avatars` exists: `POST /admin/storage/ensure_bucket`.
- Worker logs: verbose Fal submit/poll status printed; image upload logged with source.
