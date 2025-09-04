from __future__ import annotations

import time
from typing import Any


def process_image_job(agent_id: str, prompt: str) -> dict[str, Any]:
    # Placeholder: integrate Fal.AI later
    time.sleep(0.1)
    return {"status": "succeeded", "url": "https://cdn.example.com/fake.jpg", "agent_id": agent_id, "prompt": prompt}


def run_daily_event(agent_id: str, seed: int | None = None) -> dict[str, Any]:
    # Placeholder RNG and mood delta
    time.sleep(0.05)
    return {"agent_id": agent_id, "mood_delta": 0.1, "title": "A pleasant walk"}


def run_semantic_refresh(agent_id: str) -> dict[str, Any]:
    time.sleep(0.05)
    return {"agent_id": agent_id, "summary": ["Likes coffee", "Busy weekday schedule"]}

