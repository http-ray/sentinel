"""Thin Anthropic client wrapper with a graceful offline fallback.

When ``ANTHROPIC_API_KEY`` is set, :meth:`LLMClient.complete` calls the Messages
API. When it is not, ``complete`` returns ``None`` so callers fall back to a
deterministic template — keeping the whole pipeline runnable with zero API keys.
"""

from __future__ import annotations

from sentinel.config import Settings, get_settings


class LLMClient:
    """Wraps the Anthropic Messages API; no-ops (returns None) without a key."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None  # lazily constructed on first real call

    @property
    def enabled(self) -> bool:
        return self.settings.llm_enabled

    def _ensure_client(self):
        if self._client is None:
            import anthropic  # imported lazily so the dep isn't needed offline

            self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        return self._client

    def complete(
        self,
        system: str,
        prompt: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.2,
    ) -> str | None:
        """Return the model's text, or None when the LLM is disabled/unavailable."""
        if not self.enabled:
            return None
        try:
            client = self._ensure_client()
            msg = client.messages.create(
                model=self.settings.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            parts = [block.text for block in msg.content if getattr(block, "type", None) == "text"]
            text = "".join(parts).strip()
            return text or None
        except Exception as exc:  # never let LLM issues break incident response
            print(f"[llm] completion failed, falling back to template: {exc}")
            return None


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
