"""Tests for the LLM client: one provider, one call, and what it reports.

No provider is contacted: ``httpx.MockTransport`` stands in for the network.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from src.services import llm_service as llm_module
from src.services.llm_service import LlmConfig, LlmService, redact


def config(**overrides: Any) -> LlmConfig:
    values: dict[str, Any] = {
        "enabled": True,
        "model": "test-model",
        "base_url": "https://llm.local/v1",
        "api_key": "sk-secret",
    }
    values.update(overrides)
    return LlmConfig(**values)


def install_transport(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> None:
    """Reach the mock provider instead of the network."""
    real_client = httpx.AsyncClient

    def client_factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs.pop("verify", None)
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(llm_module.httpx, "AsyncClient", client_factory)


def answer(content: str, finish_reason: str | None = None) -> Callable[..., httpx.Response]:
    """A provider that answers ``content``."""

    def handler(request: httpx.Request) -> httpx.Response:
        choice: dict[str, Any] = {"message": {"content": content}}
        if finish_reason is not None:
            choice["finish_reason"] = finish_reason
        return httpx.Response(200, json={"choices": [choice]})

    return handler


# --------------------------------------------------------------------------- #
# What is asked
# --------------------------------------------------------------------------- #


async def test_the_request_carries_only_what_every_provider_takes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A parameter a model refuses turns a question it can answer into a 400."""
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    install_transport(monkeypatch, handler)

    completion = await LlmService(config()).complete([{"role": "user", "content": "hi"}])

    assert completion.text == "ok"
    assert seen == [
        {
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
            "model": "test-model",
        }
    ]


async def test_a_disabled_integration_is_never_called(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[httpx.Request] = []
    install_transport(monkeypatch, lambda request: calls.append(request) or httpx.Response(200))

    completion = await LlmService(config(enabled=False)).complete(
        [{"role": "user", "content": "hi"}]
    )

    assert completion.text is None
    assert completion.error == "the LLM integration is not configured"
    assert calls == []


# --------------------------------------------------------------------------- #
# What is reported when it fails
# --------------------------------------------------------------------------- #


async def test_a_refused_call_reports_what_the_provider_said(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_transport(
        monkeypatch,
        lambda request: httpx.Response(400, json={"error": {"message": "model not found"}}),
    )

    completion = await LlmService(config()).complete([{"role": "user", "content": "hi"}])

    assert completion.text is None
    assert completion.error is not None
    assert "HTTP 400" in completion.error
    assert "model not found" in completion.error


async def test_the_api_key_is_taken_out_of_what_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Providers quote the credential back in an authentication error."""
    install_transport(
        monkeypatch,
        lambda request: httpx.Response(401, json={"error": {"message": "bad key sk-secret"}}),
    )

    completion = await LlmService(config()).complete([{"role": "user", "content": "hi"}])

    assert completion.error is not None
    assert "sk-secret" not in completion.error
    assert "***" in completion.error


async def test_an_unreachable_provider_reports_the_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    install_transport(monkeypatch, handler)

    completion = await LlmService(config()).complete([{"role": "user", "content": "hi"}])

    assert completion.text is None
    assert completion.error is not None
    assert "ConnectError" in completion.error


async def test_an_empty_answer_is_reported_with_its_finish_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_transport(monkeypatch, answer("", finish_reason="length"))

    completion = await LlmService(config()).complete([{"role": "user", "content": "hi"}])

    assert completion.text is None
    assert completion.error is not None
    assert "empty answer" in completion.error
    assert "length" in completion.error


async def test_an_error_body_under_a_200_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A gateway answers 200 with an error object rather than a status code."""
    install_transport(
        monkeypatch,
        lambda request: httpx.Response(200, json={"error": {"message": "quota exhausted"}}),
    )

    completion = await LlmService(config()).complete([{"role": "user", "content": "hi"}])

    assert completion.text is None
    assert completion.error is not None
    assert "quota exhausted" in completion.error


def test_redact_cuts_the_message_to_a_reportable_length() -> None:
    assert redact("bad key sk-secret\n\n", "sk-secret") == "bad key ***"
    assert len(redact("x" * 500, "sk-secret")) == llm_module.MAX_ERROR_CHARS
