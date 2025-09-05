from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from openai import OpenAI
from typing import Any

from ..config import get_settings


@dataclass
class OpenAIProvider:
    model: str = "gpt-4o-mini"

    def _client(self) -> OpenAI:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY not configured")
        return OpenAI(api_key=settings.openai_api_key)

    def chat(self, system: str, messages: list[dict[str, str]]) -> str:
        client = self._client()
        # The SDK typing is strict; use Any for messages to satisfy type checker.
        msgs: list[Any] = [{"role": "system", "content": system}, *messages]
        resp = client.chat.completions.create(  # type: ignore[no-untyped-call]
            model=self.model,
            messages=msgs,
            temperature=0.7,
        )
        return resp.choices[0].message.content or ""

    def embed(self, texts: list[str]) -> list[list[float]]:
        client = self._client()
        emb = client.embeddings.create(model="text-embedding-3-small", input=texts)
        return [e.embedding for e in emb.data]
