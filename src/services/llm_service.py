"""Access to the configured LLM provider (OpenAI compatible).

The provider is configured once - environment variables as the fallback and the
``system_settings`` table as the override - and is shared by every server-side
caller: the browser proxy behind PageAgent and the release note summarizer. The
API key is only ever held here, so it never reaches a client.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.system_setting import SystemSetting
from src.utils.log import get_logger


logger = get_logger(__name__)

# Every supported provider serves the same OpenAI shaped completions resource.
COMPLETIONS_PATH = "chat/completions"
REQUEST_TIMEOUT_SECONDS = 60.0

# Settings keys that override the environment defaults, in the order they are
# applied by the admin UI.
SETTING_KEYS: tuple[str, ...] = ("llm_enabled", "llm_model", "llm_base_url", "llm_api_key")


@dataclass(frozen=True)
class LlmConfig:
    """Resolved LLM provider configuration."""

    enabled: bool
    model: str
    base_url: str
    api_key: str

    @property
    def usable(self) -> bool:
        """Whether a request can be made: enabled and fully addressed."""
        return bool(self.enabled and self.base_url and self.api_key)

    def as_dict(self, *, include_key: bool = False) -> dict[str, Any]:
        """Config as a plain dict, with the API key only when asked for."""
        payload: dict[str, Any] = {
            "enabled": self.enabled,
            "model": self.model,
            "base_url": self.base_url,
        }
        if include_key:
            payload["api_key"] = self.api_key
        return payload


async def load_llm_config(db: AsyncSession) -> LlmConfig:
    """Read the LLM configuration, database settings taking precedence over env vars.

    A database that cannot be read leaves the environment defaults in place, which
    is what keeps a summarization request from failing the whole notes request.
    """
    enabled = settings.LLM_PROXY_ENABLED
    model = settings.LLM_DEFAULT_MODEL
    base_url = settings.LLM_DEFAULT_BASE_URL
    api_key = settings.LLM_DEFAULT_API_KEY

    try:
        result = await db.execute(
            select(SystemSetting).where(
                SystemSetting.setting_key.in_(SETTING_KEYS),
                SystemSetting.is_active.is_(True),
            )
        )
        stored = {row.setting_key: (row.setting_value or "") for row in result.scalars().all()}
    except Exception as e:  # noqa: BLE001 - a broken settings read must not raise
        logger.warning(
            "LLM settings could not be read - using the environment defaults",
            extra={"error": str(e)},
        )
        return LlmConfig(enabled=enabled, model=model, base_url=base_url, api_key=api_key)

    if "llm_enabled" in stored:
        enabled = stored["llm_enabled"].strip().lower() == "true"
    if stored.get("llm_model"):
        model = stored["llm_model"]
    if stored.get("llm_base_url"):
        base_url = stored["llm_base_url"]
    if stored.get("llm_api_key"):
        api_key = stored["llm_api_key"]

    return LlmConfig(enabled=enabled, model=model, base_url=base_url, api_key=api_key)


class LlmService:
    """One provider, one call: a chat completion, or ``None`` when it fails."""

    def __init__(self, config: LlmConfig, timeout: float = REQUEST_TIMEOUT_SECONDS) -> None:
        self._config = config
        self._timeout = timeout

    @classmethod
    async def from_db(
        cls, db: AsyncSession, timeout: float = REQUEST_TIMEOUT_SECONDS
    ) -> LlmService:
        """Build the service from the configuration stored for this deployment."""
        return cls(await load_llm_config(db), timeout=timeout)

    @property
    def config(self) -> LlmConfig:
        return self._config

    async def complete(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> str | None:
        """Return the assistant message, or ``None`` when the call cannot be made.

        Every failure - disabled, unreachable, refused, empty - is logged and
        answered with ``None`` so that a caller whose LLM pass is optional can
        simply carry on without one.
        """
        if not self._config.usable:
            return None

        url = f"{self._config.base_url.rstrip('/')}/{COMPLETIONS_PATH}"
        payload: dict[str, Any] = {
            "messages": list(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if self._config.model:
            payload["model"] = self._config.model

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self._config.api_key}"},
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as e:
            logger.warning("LLM completion request failed", extra={"url": url, "error": str(e)})
            return None
        except ValueError as e:
            logger.warning(
                "LLM completion returned a body that is not JSON", extra={"error": str(e)}
            )
            return None

        choices = body.get("choices") or []
        if not choices:
            logger.warning("LLM completion returned no choices")
            return None

        content = (choices[0].get("message") or {}).get("content")
        return content if isinstance(content, str) and content.strip() else None
