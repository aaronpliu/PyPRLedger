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
HTTP_ERROR_STATUS = 400

# A provider message is carried into the log and into the reason a caller
# reports, so it is cut to a readable length and the credential is taken out of
# it - providers quote the API key back in an authentication error.
MAX_ERROR_CHARS = 300

# Settings keys that override the environment defaults, in the order they are
# applied by the admin UI.
SETTING_KEYS: tuple[str, ...] = ("llm_enabled", "llm_model", "llm_base_url", "llm_api_key")


def redact(text: str, secret: str) -> str:
    """``text`` with the API key taken out of it, cut to a reportable length."""
    if secret:
        text = text.replace(secret, "***")
    return " ".join(text.split())[:MAX_ERROR_CHARS]


@dataclass(frozen=True)
class Completion:
    """One answer from the provider, or why there is none.

    A pass that is optional still has to say why it produced nothing: answering
    with a plain ``None`` makes a refused call read the same as one that was
    never made, and leaves nobody anything to act on.
    """

    text: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class LlmConfig:
    """Resolved LLM provider configuration."""

    enabled: bool
    model: str
    base_url: str
    api_key: str

    @property
    def unusable_reason(self) -> str | None:
        """Why no request can be made, or ``None`` when one can.

        An API key is not required: a model served on localhost - the usual
        deployment - takes no credential, and demanding one kept the client from
        calling a provider that was configured and answering.
        """
        if not self.enabled:
            return "the LLM integration is disabled"
        if not self.base_url:
            return "no LLM base URL is configured"
        return None

    @property
    def usable(self) -> bool:
        """Whether a request can be made: enabled and addressed."""
        return self.unusable_reason is None

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
    """One provider, one call: a chat completion, or the reason there is none."""

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

    async def complete(self, messages: Sequence[dict[str, str]]) -> Completion:
        """Ask for one completion.

        Only what every OpenAI shaped provider takes is sent - the messages and,
        when one is configured, the model. A parameter a given model refuses
        (``temperature``, ``max_tokens``) turns a question it can answer into a
        400, and how long an answer may be is the provider's to decide.
        """
        reason = self._config.unusable_reason
        if reason is not None:
            return Completion(error=reason)

        url = f"{self._config.base_url.rstrip('/')}/{COMPLETIONS_PATH}"
        payload: dict[str, Any] = {"messages": list(messages), "stream": False}
        if self._config.model:
            payload["model"] = self._config.model

        # Only sent when there is one: a model on localhost takes no credential,
        # and an empty `Bearer ` is something providers refuse.
        headers: dict[str, str] = {}
        if self._config.api_key:
            headers["Authorization"] = f"Bearer {self._config.api_key}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as e:
            error = redact(f"{type(e).__name__}: {e}", self._config.api_key)
            logger.warning("LLM completion request failed", extra={"url": url, "error": error})
            return Completion(error=error)

        # The body is what names the problem - an unknown model, a bad key, a
        # prompt longer than the model takes - so it is read before anything else.
        if response.status_code >= HTTP_ERROR_STATUS:
            error = redact(response.text, self._config.api_key)
            logger.warning(
                "LLM completion was refused by the provider",
                extra={"url": url, "status": response.status_code, "body": error},
            )
            return Completion(error=f"HTTP {response.status_code}: {error}")

        try:
            body = response.json()
        except ValueError as e:
            error = redact(response.text, self._config.api_key)
            logger.warning(
                "LLM completion returned a body that is not JSON",
                extra={"body": error, "error": str(e)},
            )
            return Completion(error=f"the response is not JSON: {error}")
        if not isinstance(body, dict):
            return Completion(error="the response is not a JSON object")

        choices = body.get("choices") or []
        if not choices:
            # a gateway that answers 200 with an error object says it here
            error = redact(
                str(body.get("error") or "the response holds no choices"), self._config.api_key
            )
            logger.warning("LLM completion returned no choices", extra={"body": error})
            return Completion(error=error)

        choice = choices[0]
        # A provider that stopped mid-answer says so here, rather than leaving the
        # caller to infer it from an answer that does not parse
        if choice.get("finish_reason") == "length":
            logger.warning("LLM completion was cut off by the provider's token limit")

        content = (choice.get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
            reason = redact(str(choice.get("finish_reason")), self._config.api_key)
            logger.warning(
                "LLM completion returned an empty answer", extra={"finish_reason": reason}
            )
            return Completion(error=f"the provider returned an empty answer ({reason})")
        return Completion(text=content)
