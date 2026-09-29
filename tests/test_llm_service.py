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
    request_url: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        request_url.append(str(request.url))
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
    # the URL the request went to: the base URL with the resource appended
    assert request_url == ["https://llm.local/v1/chat/completions"]


async def test_a_model_without_an_api_key_is_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A model served on localhost takes no credential.

    Regression: demanding a key kept the client from calling a provider that was
    configured and answering - the request never left the process, so the
    provider logged nothing at all.
    """
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    install_transport(monkeypatch, handler)

    completion = await LlmService(config(api_key="")).complete([{"role": "user", "content": "hi"}])

    assert completion.text == "ok"
    assert len(seen) == 1
    # and an empty `Bearer ` - which providers refuse - is not sent either
    assert "authorization" not in {key.lower() for key in seen[0].headers}


async def test_a_configured_key_is_sent_as_a_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    install_transport(monkeypatch, handler)

    await LlmService(config()).complete([{"role": "user", "content": "hi"}])

    assert seen[0].headers["authorization"] == "Bearer sk-secret"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"enabled": False}, "the LLM integration is disabled"),
        ({"base_url": ""}, "no LLM base URL is configured"),
    ],
)
async def test_an_unusable_configuration_says_which_piece_is_missing(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, Any], reason: str
) -> None:
    """A skipped pass has to name what to configure, or it reads as a failure."""
    calls: list[httpx.Request] = []
    install_transport(monkeypatch, lambda request: calls.append(request) or httpx.Response(200))

    completion = await LlmService(config(**overrides)).complete([{"role": "user", "content": "hi"}])

    assert completion.text is None
    assert completion.error == reason
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
