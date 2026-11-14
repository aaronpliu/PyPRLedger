"""Production hardening guard rails in :class:`Settings`.

A production instance must not boot with development defaults: a known
SECRET_KEY allows forging a JWT for any user, and a wildcard CORS origin with
credentials lets any site call the API as the reader.
"""

import pytest
from pydantic import ValidationError

from src.core.config import Settings


GOOD_SECRET = "s" * 48
GOOD_SALT = "a-unique-id-obfuscator-salt"


def build_settings(**overrides) -> Settings:
    """Build production settings with all guards satisfied, unless overridden."""
    values: dict[str, object] = {
        "ENV": "production",
        "SECRET_KEY": GOOD_SECRET,
        "BACKEND_CORS_ORIGINS": "https://prledger.example.com",
        "ID_OBFUSCATOR_SALT": GOOD_SALT,
        "DEBUG": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_with_hardened_values_is_accepted():
    settings = build_settings()

    assert settings.ENV == "production"
    assert settings.backend_cors_origins_list == ["https://prledger.example.com"]


def test_production_rejects_default_secret_key():
    with pytest.raises(ValidationError) as excinfo:
        build_settings(SECRET_KEY="development-secret-key-change-in-production")

    assert "SECRET_KEY" in str(excinfo.value)


def test_production_rejects_short_secret_key():
    with pytest.raises(ValidationError) as excinfo:
        build_settings(SECRET_KEY="too-short")

    assert "SECRET_KEY" in str(excinfo.value)


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError) as excinfo:
        build_settings(BACKEND_CORS_ORIGINS="*")

    assert "BACKEND_CORS_ORIGINS" in str(excinfo.value)


def test_production_rejects_debug_mode():
    with pytest.raises(ValidationError) as excinfo:
        build_settings(DEBUG=True)

    assert "DEBUG" in str(excinfo.value)


def test_production_rejects_default_obfuscator_salt():
    with pytest.raises(ValidationError) as excinfo:
        build_settings(ID_OBFUSCATOR_SALT="change-me-in-production")

    assert "ID_OBFUSCATOR_SALT" in str(excinfo.value)


def test_development_is_not_held_to_production_rules():
    # A development instance may keep whatever key the environment provides:
    # the guard exists to keep production safe, not to break local runs.
    settings = Settings(ENV="development")

    assert settings.ENV == "development"
