from __future__ import annotations

import time
from typing import Any
import json
import asyncio
import time
import os
import requests

from api.withme.db import session_scope
from api.withme.models import ImageJob, Message, Agent
from api.withme.services.storage import upload_public_image_from_url


def _extract_url(obj: Any) -> str | None:
    """Try to find an HTTP(s) URL nested anywhere in a JSON-like object."""
    if isinstance(obj, str) and obj.startswith("http"):
        return obj
    if isinstance(obj, dict):
        # common keys first
        for k in ("image", "url", "image_url", "output_url"):
            if k in obj and isinstance(obj[k], str) and obj[k].startswith("http"):
                return obj[k]
        for v in obj.values():
            u = _extract_url(v)
            if u:
                return u
    if isinstance(obj, list):
        for it in obj:
            u = _extract_url(it)
            if u:
                return u
    return None


def process_image_job(image_job_id: str) -> dict[str, Any]:
    """
    Submit prompt to Fal.AI queues and poll for result.
    Run all async DB work in a single event loop to avoid cross-loop issues.
    """
    from api.withme.config import get_settings
    from uuid import UUID

    async def async_main() -> dict[str, Any]:
        settings = get_settings()
        api_key = settings.fal_api_key
        print(f"[worker] process_image_job start job_id={image_job_id} key_present={bool(api_key)}")
        url: str | None = None

        # Fetch job and agent context
        prompt = None
        kind = 'gen'
        agent_id = None
        base_image_url = None
        appearance_prompt = None
        persona_summary = None

        async with session_scope() as session:
            try:
                jid = UUID(str(image_job_id))
            except Exception:
                jid = None
            job = await session.get(ImageJob, jid) if jid else None
            if not job:
                print(f"[worker] Job not found job_id={image_job_id}")
            else:
                prompt = job.prompt
                kind = job.kind or 'gen'
                agent_id = str(job.agent_id)
                ag = await session.get(Agent, job.agent_id)
                if ag and isinstance(ag.persona_json, dict):
                    base_image_url = ag.base_image_url
                    appearance_prompt = (
                        ag.persona_json.get("appearance", {}).get("base_image_prompt")
                        if isinstance(ag.persona_json.get("appearance"), dict) else None
                    )
                    summary = ag.persona_json.get("summary") or ""
                    traits = ", ".join(ag.persona_json.get("traits", [])[:5])
                    persona_summary = f"{summary}. Traits: {traits}."
        print(f"[worker] Loaded job kind={kind} prompt_present={bool(prompt)} agent={agent_id}")

        # Prepare prompt
        if not api_key:
            url = None
        else:
            style_guard = (
                "PG-13, no explicit content, no nudity, tasteful, cinematic lighting, fully clothed,"
                " avoid fetishized depictions."
            )
            if not prompt:
                if kind == 'base':
                    prompt = appearance_prompt or "portrait, warm lighting, natural look"
                    print(f"[worker] Synthesized base prompt len={len(prompt)}")
                else:
                    prompt = "Selfie perspective; subject in a natural indoor setting; friendly expression; chest-up framing."
                    print(f"[worker] Synthesized edit prompt len={len(prompt)}")
            headers = {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}

            try:
                if kind == 'edit' and base_image_url:
                    edit_prompt = f"{prompt}. {style_guard}"
                    if persona_summary:
                        edit_prompt = f"{edit_prompt} Persona aesthetics: {persona_summary}"
                    print(f"[worker] Submitting Fal EDIT job for agent={agent_id} prompt_len={len(edit_prompt)} base_url_present={bool(base_image_url)}")
                    submit = requests.post(
                        "https://queue.fal.run/fal-ai/nano-banana/edit",
                        json={"image_url": base_image_url, "prompt": edit_prompt, "metadata": {"job_id": image_job_id}},
                        headers=headers,
                        timeout=15,
                    )
                else:
                    full_prompt = f"{prompt}. {style_guard}"
                    if persona_summary:
                        full_prompt = f"{full_prompt} Persona aesthetics: {persona_summary}"
                    print(f"[worker] Submitting Fal GEN job (Flux) for agent={agent_id} prompt_len={len(full_prompt)} kind={kind}")
                    submit = requests.post(
                        "https://queue.fal.run/fal-ai/flux-pro/v1.1-ultra",
                        json={"prompt": full_prompt, "metadata": {"job_id": image_job_id}},
                        headers=headers,
                        timeout=10,
                    )
                submit.raise_for_status()
                # Log submit response content-type and small snippet
                sub_ct = (submit.headers.get("content-type") or "").lower()
                sub_txt = submit.text or ""
                print(f"[worker] Fal submit resp ct={sub_ct} len={len(sub_txt)} snip={sub_txt[:200].replace('\n',' ')}")
                data = {}
                try:
                    data = submit.json()
                except Exception as e:
                    print(f"[worker] Fal submit JSON parse failed: {e}")
                req_id = data.get("request_id") or data.get("id")
                status_url = data.get("status_url") or data.get("statusUrl")
                response_url = data.get("response_url") or data.get("responseUrl")
                print(f"[worker] Fal submit ok job_id={image_job_id} request_id={req_id} keys={list(data.keys())}")
            except Exception as e:
                print(f"[worker] Fal call failed: {e}")
                req_id = None

            # Mark running
            try:
                async with session_scope() as session:
                    if 'jid' in locals() and jid:
                        j = await session.get(ImageJob, jid)
                        if j:
                            j.status = "running"
            except Exception as e:
                print(f"[worker] mark running failed: {e}")

            # Poll Fal for result
            poll_endpoint = status_url or (f"https://queue.fal.run/requests/{req_id}" if req_id else None)
            if poll_endpoint:
                poll_headers = {**headers, "Accept": "application/json, text/event-stream"}
                for i in range(30):
                    time.sleep(2)
                    r = requests.get(poll_endpoint, headers=poll_headers, timeout=15)
                    if r.status_code >= 500:
                        continue
                    j = None
                    ct = (r.headers.get("content-type") or "").lower()
                    try:
                        if "application/json" in ct:
                            j = r.json()
                        else:
                            txt = r.text or ""
                            # Debug snippet of poll body
                            if i in (0, 1, 2) or i % 5 == 0:
                                print(f"[worker] Fal poll raw ct={ct} len={len(txt)} snip={txt[:200].replace('\n',' ')}")
                            parsed = None
                            # Handle SSE style payloads: lines starting with "data: {json}"
                            for line in txt.splitlines():
                                line = line.strip()
                                if line.startswith("data:"):
                                    payload = line[5:].strip()
                                    try:
                                        parsed = json.loads(payload)
                                    except Exception:
                                        continue
                            if parsed is None and txt:
                                try:
                                    parsed = json.loads(txt)
                                except Exception:
                                    print(f"[worker] Fal poll non-JSON response ct={ct} len={len(txt)}")
                            j = parsed if parsed is not None else {}
                    except Exception as e:
                        print(f"[worker] Fal poll parse failed: {e}")
                        j = {}
                    status = (j.get("status") or "").lower()
                    if i == 0 or status in {"succeeded","completed","success","failed","error"}:
                        print(f"[worker] Fal poll status job_id={image_job_id} status={status} keys={list(j.keys())}")
                    if status in {"succeeded", "completed", "success"}:
                        # Prefer dedicated response endpoint if provided
                        if response_url:
                            try:
                                r2 = requests.get(response_url, headers=headers, timeout=20)
                                resp_ct = (r2.headers.get("content-type") or "").lower()
                                resp_txt = r2.text or ""
                                print(f"[worker] Fal response endpoint ct={resp_ct} len={len(resp_txt)} snip={resp_txt[:200].replace('\n',' ')}")
                                try:
                                    j2 = r2.json()
                                except Exception as e:
                                    print(f"[worker] Fal response json parse failed: {e}")
                                    j2 = {}
                                result = j2.get("response") or j2
                                url = _extract_url(result)
                                print(f"[worker] Fal response endpoint provided URL={bool(url)}")
                            except Exception as e:
                                print(f"[worker] Fal response request failed: {e}")
                        # Fallback to extracted from status payload if no response url or no url
                        if not url:
                            result = j.get("response") or j.get("result") or j
                            url = _extract_url(result)
                            print(f"[worker] Fal poll success extracted_url={bool(url)} (fallback)")
                        break
                    # Fallback: attempt response endpoint if status missing
                    if not status and response_url and not url:
                        try:
                            r2 = requests.get(response_url, headers=headers, timeout=20)
                            if r2.ok:
                                try:
                                    resp_ct = (r2.headers.get("content-type") or "").lower()
                                    resp_txt = r2.text or ""
                                    print(f"[worker] Fal response endpoint ct={resp_ct} len={len(resp_txt)} snip={resp_txt[:200].replace('\n',' ')}")
                                    j2 = r2.json()
                                    result = j2.get("response") or j2
                                    url = _extract_url(result)
                                    if url:
                                        print(f"[worker] Fal response endpoint provided URL=true")
                                        break
                                except Exception as e:
                                    print(f"[worker] Fal response parse failed: {e}")
                        except Exception as e:
                            print(f"[worker] Fal response request failed: {e}")
                    if status in {"failed", "error"}:
                        break

        if url is None:
            url = "https://picsum.photos/seed/withme/512/768"

        # Persist result
        try:
            async with session_scope() as session:
                if 'jid' not in locals():
                    try:
                        jid = UUID(str(image_job_id))
                    except Exception:
                        jid = None
                job = await session.get(ImageJob, jid) if jid else None
                if job:
                    job.status = "succeeded" if url else "failed"
                    job.result_url = url
                    ag = await session.get(Agent, job.agent_id)
                    if ag:
                        if (job.kind or 'gen') == 'base':
                            print(f"[worker] Uploading base image to Supabase for agent={ag.id}")
                            public_url = upload_public_image_from_url(url)
                            ag.base_image_url = public_url or url
                            print(f"[worker] Base image set agent={ag.id} url={'uploaded' if public_url else 'fal_url'}")
                        else:
                            msg = Message(user_id=ag.user_id, agent_id=ag.id, role="agent", text=None, image_url=url)
                            session.add(msg)
                            print(f"[worker] Added agent image message agent={ag.id} url_len={len(url)}")
        except Exception as e:
            print(f"[worker] update failed: {e}")
        print(f"[worker] process_image_job done job_id={image_job_id} url_present={bool(url)}")
        return {"status": "succeeded" if url else "failed", "url": url, "image_job_id": image_job_id}

    return asyncio.run(async_main())


def run_daily_event(agent_id: str, seed: int | None = None) -> dict[str, Any]:
    # Placeholder RNG and mood delta
    time.sleep(0.05)
    return {"agent_id": agent_id, "mood_delta": 0.1, "title": "A pleasant walk"}


def run_semantic_refresh(agent_id: str) -> dict[str, Any]:
    time.sleep(0.05)
    return {"agent_id": agent_id, "summary": ["Likes coffee", "Busy weekday schedule"]}
