# With Me — MVP PRD v0.1

*Last updated: 2025‑09‑04*

## 0) Summary & Goals

**With Me** is a text‑first AI companion/romance chat app. MVP delivers:

* One agent per user
* Hidden **affinity** influences tone, initiations, and image access
* **Episodic** + **semantic** memory (permanent)
* **Offline life** with daily mood and rare life events (5% chance/day)
* **Scenario tracks (A–D)** guiding long/medium/short/micro arcs
* **PG‑13** content; 18+ gate; optional **no‑romance** flag per agent
* Push‑initiated messages via FCM

## 1) Scope (MVP)

### In

* Text chat, optional AI‑generated images (Fal.AI) gated by affinity & romance flag
* FastAPI backend; Flutter app as primary client; simple web test UI
* Supabase Postgres + Auth; Pinecone retrieval; Redis for jobs/queues
* Daily event generation (LLM) with mood deltas; timezone = user’s
* Admin panel: create/edit agents, persona, traits, scenario seeds, flags

### Out (Non‑Goals for MVP)

* Voice, phone/video calls, multi‑agent per user, analytics, manual admin events, journals/timelines UI, multi‑language, complex moderation beyond basic policies

## 2) Personas

* **End User**: seeks companionship; expects believable, timely, warm (or aloof) behavior true to persona
* **Admin/Operator**: seeds agents, tunes thresholds, reviews behavior (read‑only logs)

## 3) Functional Requirements

### 3.1 Chat UX

* Modern messaging UI (text + image bubbles)
* Agent replies depend on **persona + mood + scenarios + memories**
* *No* separate journal or memory viewer in MVP

### 3.2 Images

* On explicit user request; allowed if `affinity ≥ threshold` and `romance_allowed = true`
* Uses Fal.AI workflow with PG‑13 style guide; result stored as CDN URL

### 3.3 Affinity (Hidden)

* Float `[0,1]` starting at `0.30`
* Updated each turn by weighted features (see §7)
* Thresholds: `0.60` (images), `0.75` (warmer tone + more initiations), `≤0.25` (cooler)

### 3.4 Mood & Offline Life

* Mood float `[-1, +1]`; daily baseline with deltas
* Availability windows (local user time): 07–09 commute, 09–17 work, 18–23 evening, 23–07 sleep
* One RNG event/day with **5%** probability; each event carries `mood_delta` and optional topic hooks
* Message length/latency adapt by window (shorter at work, delayed at night)

### 3.5 Scenarios (A–D tracks)

* **A** (Long arc): e.g., become CEO
* **B** (Medium): pursue romance
* **C** (Short): resolve family drama
* **D** (Micro): buying a car
* Tracks are **soft constraints**; LLM can deviate using RNG and current state

### 3.6 Initiations (Push)

* Agents may initiate based on personality + mood + affinity + cooldowns
* Delivery via FCM; tap opens chat; server posts first message on open (or pre‑push message if desired)

### 3.7 Safety

* 18+ acknowledgement required (timestamped)
* PG‑13 images and text
* Per‑agent **no‑romance** flag enforced in logic & prompts

### 3.8 Admin Panel (simple)

* Create/edit agent: name, persona JSON, traits, likes/dislikes, initiation tendency, thresholds, flags
* Seed/regen scenarios (A–D) with LLM
* Read‑only: last mood/affinity, last event, recent messages

## 4) Non‑Functional Requirements

* **Latency**: p95 agent reply under 2.5s (excl. image gen)
* **Uptime**: 99% (single node), graceful restart
* **Privacy**: store raw text of memories; permanent retention (MVP)
* **Security**: Supabase Auth (JWT), RLS on tables; per‑endpoint rate limits

## 5) Architecture Overview

* **API**: FastAPI service (REST)
* **Worker**: background jobs (Celery/RQ) for image, events, semantic refresh
* **DB**: Supabase Postgres (managed)
* **Cache/Queue**: Redis
* **Vector**: Pinecone (`text-embedding-3-small`, 1536‑d)
* **LLM**: OpenAI (chat, summarization, event gen); provider abstraction layer
* **Push**: Firebase Cloud Messaging (FCM); keep Supabase Auth

```
Flutter/Web ──REST──▶ FastAPI ──▶ Redis Queue ─▶ Worker
      │                      │                 │
      │                      ├─▶ Postgres ◀───┘
      │                      ├─▶ Pinecone
      │                      ├─▶ OpenAI (LLM)
      │                      └─▶ Fal.AI (images)
      └─ FCM ◀───────────────┘
```

## 6) Data Model (ERD summary)

* **users**(…)
* **user\_devices**(user\_id, platform, fcm\_token, last\_seen\_at)
* **agents**(user\_id, persona\_json, mood, affinity, … flags)
* **messages**(user\_id, agent\_id, role, text, image\_url)
* **events**(agent\_id, type, payload\_json, mood\_delta, seed)
* **scenarios**(agent\_id, track, title, state\_json, progress)
* **semantic\_memory**(agent\_id, content)
* **affinity\_deltas**(agent\_id, message\_id, feature, delta)
* **image\_jobs**(agent\_id, prompt, status, result\_url)

### 6.1 DDL (Postgres)

```sql
create table users (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  dob_verified_at timestamptz,
  created_at timestamptz not null default now()
);

create table user_devices (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  platform text check (platform in ('android','ios','web')),
  fcm_token text not null,
  last_seen_at timestamptz,
  unique(user_id, fcm_token)
);

create table agents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  name text not null,
  persona_json jsonb not null,
  romance_allowed boolean not null default false,
  initiation_tendency real not null default 0.4,
  image_threshold real not null default 0.6,
  mood real not null default 0.0,
  affinity real not null default 0.3,
  last_mood_update_at timestamptz,
  created_at timestamptz not null default now()
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  agent_id uuid references agents(id) on delete cascade,
  role text check (role in ('user','agent')) not null,
  text text,
  image_url text,
  created_at timestamptz not null default now()
);

create table events (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references agents(id) on delete cascade,
  type text not null,
  payload_json jsonb not null,
  mood_delta real not null,
  seed bigint not null,
  occurred_at timestamptz not null default now()
);

create table scenarios (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references agents(id) on delete cascade,
  track text check (track in ('A','B','C','D')) not null,
  title text not null,
  state_json jsonb not null,
  progress real not null default 0.0,
  updated_at timestamptz not null default now()
);

create table semantic_memory (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references agents(id) on delete cascade,
  content text not null,
  updated_at timestamptz not null default now()
);

create table affinity_deltas (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references agents(id) on delete cascade,
  message_id uuid references messages(id) on delete cascade,
  feature text not null,
  delta real not null,
  created_at timestamptz not null default now()
);

create table image_jobs (
  id uuid primary key default gen_random_uuid(),
  agent_id uuid references agents(id) on delete cascade,
  prompt text not null,
  status text check (status in ('queued','running','succeeded','failed')) not null,
  result_url text,
  created_at timestamptz not null default now()
);
```

> **RLS**: enable on `messages`, `events`, `scenarios`, `semantic_memory`, `image_jobs`, `affinity_deltas` to restrict by `user_id` via join to `agents`.

## 7) Behavior & Algorithms

### 7.1 Affinity Update (deterministic)

Let `A∈[0,1]`. After each agent turn:

```
ΔA = w_emp*Emp + w_cont*Cont + w_align*Align − w_bound*Bound + w_event*Support
A' = clamp( A + σ(ΔA), 0, 1 )
```

Where:

* **Emp**: user empathy detected (0..1)
* **Cont**: continuity (references to past names/events/goals) (0..1)
* **Align**: preference alignment detected (0..1)
* **Bound**: boundary violations (0..1)
* **Support**: user was supportive during negative event (0..1)
* σ: small logistic smoothing (e.g., `σ(x)=tanh(x/3)/10`)
* Defaults: `w_emp=0.10, w_cont=0.08, w_align=0.06, w_bound=0.15, w_event=0.07`
* Log each component to `affinity_deltas`

### 7.2 Mood Update

Daily baseline `M0` (carryover with small decay `λ=0.1`), then apply events and chat micro‑deltas:

```
M_today = clamp( (1-λ)*M_yesterday + Σ event_deltas + ε_chat , -1, 1 )
```

### 7.3 Initiation Probability

Per eligible window, compute:

```
P = base * sigm(k1*(A-0.5)) * sigm(k2*M) * window_factor * cooldown_factor
```

* `base = initiation_tendency` (persona)
* `sigm(z)=1/(1+e^{-z})` with `k1=4, k2=3`
* `window_factor`: commute 1.1, work 0.5, evening 1.3, sleep 0.1
* `cooldown_factor`: 0 if sent within last 2h; otherwise 1
* Apply daily cap (e.g., max 2 initiations/day)

### 7.4 Retrieval Policy

* **Recency**: last 20 messages
* **Semantic**: Pinecone top‑K=8 (hybrid union, de‑dupe by id)
* Include **active scenarios**, **mood**, **availability**, **user safety flags**

## 8) API Spec (FastAPI)

> Auth via Supabase (JWT). All endpoints require `Authorization: Bearer <jwt>` unless noted.

### 8.1 Public

* `POST /auth/supabase/webhook` — (optional) auth events (sign‑ups)

### 8.2 Device & State

* `POST /device/fcm` — register/refresh FCM token

  * **Req** `{ "platform":"android|ios|web", "token":"..." }`
  * **Res** `204 No Content`

* `GET /state` — lightweight state snapshot

  * **Res** `{ "agent_id":"...", "availability":"work|commute|evening|sleep", "mood":0.1, "romance_allowed":true }`

### 8.3 Agent

* `GET /agent` — safe snapshot (no hidden affinity)

  * **Res** `{ "id":"...", "name":"Daniel", "persona":{...}, "romance_allowed":true }`

### 8.4 Chat

* `POST /chat/send`

  * **Req** `{ "text":"How was your day?" }`
  * **Res** `{ "message_id":"...", "reply": { "text":"Just finished a tough meeting...", "image_url":null } }`

* `POST /chat/request_image`

  * **Req** `{ "prompt":"Selfie at the cafe" }`
  * **Res** `{ "job_id":"...", "status":"queued" }`

* `POST /webhooks/fal`  (Fal.AI → server)

  * **Req** `{ "job_id":"...", "status":"succeeded|failed", "url":"https://..." }`
  * **Res** `204`

### 8.5 Admin

* `POST /admin/agent`

  * **Req** `{ "name":"Daniel", "persona":{...}, "romance_allowed":true, "initiation_tendency":0.25 }`
  * **Res** `{ "id":"..." }`

* `PATCH /admin/agent/{id}` — edit persona/flags/thresholds

* `POST /admin/scenarios/seed` — LLM generates tracks A–D

  * **Req** `{ "agent_id":"...", "seeds": { "A":{...}, "B":{...}, "C":{...}, "D":{...} } }`

### 8.6 Cron (secured by internal token)

* `POST /cron/daily_event` — hourly sweep to simulate “06:00 local” per agent and run RNG
* `POST /cron/semantic_refresh` — nightly

### 8.7 Errors

* `400` invalid payload; `401/403` auth; `429` rate limit; `503` provider down

## 9) Prompt Contracts (v1)

### RESPOND\_v1 (chat)

```
System: You are {agent.name}, an AI companion. Persona: {persona}. Safety: PG-13; no explicit content. Romance allowed: {romance_allowed}.
State: mood={mood}, availability={availability}, scenarios={summarized_tracks}.
Memories (semantic): {semantic_summary}
Memories (episodic excerpts): {topK_memories}
User message: {user_text}
Style: Vary length by availability; stay in-character; show continuity; avoid over-eagerness unless affinity is high.
Output JSON: {"text": "..."}
```

### EVENT\_v1 (daily event generator)

```
System: Generate 0 or 1 event for {agent.name} today. Probability guidance: 5% chance. If event, include:
{"title":"...","summary":"...","mood_delta":-0.1..+0.3,"topics":["..."],"privacy":"internal"}
Respect persona and current scenarios.
```

### SEMANTIC\_REFRESH\_v1

```
Summarize stable facts and preferences learned since last update. Output short bullet list paragraphs.
```

## 10) Moderation & Safety

* Text moderation pass (LLM/light rules) for both input and output; block disallowed image prompts server‑side
* PG‑13 Fal.AI style guard; prohibited keywords filter
* 18+ gate; disclaimer in app settings

## 11) Scheduling & Timezones

* Store each agent’s timezone = user’s current tz
* **Hourly Cron** for `daily_event`: for each agent, if local time crosses 06:00 since last run → roll RNG; ensures per‑timezone execution without N crons

## 12) Push Initiations

* Scheduler runs every 30 min; compute `P` (§7.3). If pass and cooldown ok → create notification
* Template examples: “Just got out of a meeting—got a minute?”, “Commute was chaotic today… how’s your morning?”

## 13) Fal.AI Integration

* Server → Fal.AI: include persona descriptors; PG‑13 guardrails; attach `job_id`
* Webhook updates `image_jobs` and appends an agent message with `image_url`

## 14) Web Test UI (simple)

* Minimal React or plain HTML page with: login (Supabase), chat area, request image button, toggle to show `/state` snapshot for QA

## 15) Deployment (Single‑Node Kubernetes)

> Use managed Supabase Postgres. Only deploy API, Worker, Redis. Ingress optional.

### 15.1 Secrets (example placeholders)

```
apiVersion: v1
kind: Secret
metadata: { name: withme-secrets }
type: Opaque
data:
  OPENAI_API_KEY: <base64>
  PINECONE_API_KEY: <base64>
  FAL_API_KEY: <base64>
  SUPABASE_JWT_SECRET: <base64>
  SUPABASE_URL: <base64>
  REDIS_URL: <base64>  # e.g., redis://redis:6379/0
  FCM_SERVER_KEY: <base64>
```

### 15.2 API Deployment & Service

```
apiVersion: apps/v1
kind: Deployment
metadata: { name: api, labels: { app: withme } }
spec:
  replicas: 2
  selector: { matchLabels: { app: withme, tier: api } }
  template:
    metadata: { labels: { app: withme, tier: api } }
    spec:
      containers:
        - name: api
          image: ghcr.io/withme/api:0.1.0
          ports: [ { containerPort: 8080 } ]
          envFrom: [ { secretRef: { name: withme-secrets } } ]
          readinessProbe: { httpGet: { path: /health, port: 8080 }, initialDelaySeconds: 5, periodSeconds: 10 }
          livenessProbe:  { httpGet: { path: /health, port: 8080 }, initialDelaySeconds: 15, periodSeconds: 20 }
---
apiVersion: v1
kind: Service
metadata: { name: api }
spec:
  selector: { app: withme, tier: api }
  ports: [ { port: 80, targetPort: 8080 } ]
```

### 15.3 Worker Deployment

```
apiVersion: apps/v1
kind: Deployment
metadata: { name: worker, labels: { app: withme } }
spec:
  replicas: 1
  selector: { matchLabels: { app: withme, tier: worker } }
  template:
    metadata: { labels: { app: withme, tier: worker } }
    spec:
      containers:
        - name: worker
          image: ghcr.io/withme/worker:0.1.0
          command: ["python","-m","worker.run"]
          envFrom: [ { secretRef: { name: withme-secrets } } ]
```

### 15.4 Redis

```
apiVersion: apps/v1
kind: Deployment
metadata: { name: redis }
spec:
  replicas: 1
  selector: { matchLabels: { app: redis } }
  template:
    metadata: { labels: { app: redis } }
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports: [ { containerPort: 6379 } ]
---
apiVersion: v1
kind: Service
metadata: { name: redis }
spec:
  selector: { app: redis }
  ports: [ { port: 6379, targetPort: 6379 } ]
```

### 15.5 Ingress (optional)

```
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  rules:
    - host: api.withme.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend: { service: { name: api, port: { number: 80 } } }
```

### 15.6 CronJobs

```
apiVersion: batch/v1
kind: CronJob
metadata: { name: daily-event }
spec:
  schedule: "0 * * * *"   # hourly sweep
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: sweeper
              image: ghcr.io/withme/cron:0.1.0
              command: ["python","-m","cron.daily_event"]
              envFrom: [ { secretRef: { name: withme-secrets } } ]
          restartPolicy: OnFailure
---
apiVersion: batch/v1
kind: CronJob
metadata: { name: semantic-refresh }
spec:
  schedule: "30 2 * * *"  # nightly
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: refresher
              image: ghcr.io/withme/cron:0.1.0
              command: ["python","-m","cron.semantic_refresh"]
              envFrom: [ { secretRef: { name: withme-secrets } } ]
          restartPolicy: OnFailure
```

## 16) Observability & Ops

* Structured logs with `conversation_id`, token counts, provider latency/cost
* Health endpoint `/health`; readiness gate Pinecone & DB checks
* Basic rate limits: `20 req/min` per user on chat

## 17) Rollout Plan

* **Week 1**: API skeleton; DDL; Pinecone; chat path with retrieval; affinity/mood v0
* **Week 2**: Admin panel; scenarios A–D seeding; event cron; FCM initiations
* **Week 3**: Fal.AI; semantic refresh; PG‑13 moderation; prompts v1 tuning
* **Week 4**: Flutter polish; K8s deploy; smoke & beta test

## 18) Risks & Mitigations

* **Provider drift / lock‑in** → abstraction layer; store model metadata; re‑embed plan
* **Push spam** → cooldowns, caps, mood/affinity gating
* **Token/cost spikes** → strict context limits; summarize aggressively; embed selectively
* **Safety leakage** → dual guardrails: prompt + server filters; “no‑romance” hard check

## 19) Default Config (MVP)

* `affinity.image_threshold = 0.60`
* `agent.initiation_tendency = { Daniel: 0.25, Needy: 0.65 }`
* `daily_event.probability = 0.05`
* `initiation.daily_cap = 2`
* `retrieval.recency_last_n = 20; semantic_top_k = 8`

---

**Appendix A — Example FastAPI Handlers (pseudo‑sigs)**

```py
@app.post('/chat/send')
async def send_chat(req: ChatReq, user=Depends(auth)):
    agent = get_agent(user.id)
    ctx = build_context(agent, req.text)
    reply = llm.respond(ctx)
    save_messages(user, agent, req.text, reply.text)
    update_affinity(agent, req.text, reply.text)
    return {"message_id": ..., "reply": {"text": reply.text}}
```

**Appendix B — Fal.AI Style Guide (PG‑13)**

* No nudity; no minors; no explicit sexual content; avoid fetishized depictions
* Cinematic, tasteful, fully clothed, romantic tones allowed if `romance_allowed`
* Use persona aesthetics; avoid real‑person likeness

