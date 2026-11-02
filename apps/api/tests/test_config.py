"""Configuration validation tests."""

import pytest
from pydantic import ValidationError

from vaultline_api.core.config import Settings


def test_settings_parse_comma_separated_origins() -> None:
    settings = Settings(cors_allowed_origins="http://localhost:3000, https://example.test")

    assert settings.cors_allowed_origins == ["http://localhost:3000", "https://example.test"]


def test_settings_reject_unknown_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="localish")


def test_settings_reject_empty_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="")


def test_database_url_escapes_credentials_and_validates_port() -> None:
    settings = Settings(database_user="vault user", database_password="p@ss/word")

    assert "vault+user:p%40ss%2Fword@" in settings.database_url

    with pytest.raises(ValidationError):
        Settings(database_port=70000)
