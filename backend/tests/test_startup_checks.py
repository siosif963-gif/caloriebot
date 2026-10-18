"""Проверки конфигурации при старте."""
import pytest
from fastapi.testclient import TestClient

from config import settings
from main import app, check_startup_settings


def _configure(monkeypatch, *, dev_mode: bool, token: str):
    monkeypatch.setattr(settings, "DEV_MODE", dev_mode)
    monkeypatch.setattr(settings, "BOT_TOKEN", token)


def test_dev_mode_with_bot_token_is_refused(monkeypatch):
    _configure(monkeypatch, dev_mode=True, token="123456:REAL_LOOKING_TOKEN")
    with pytest.raises(RuntimeError, match="DEV_MODE"):
        check_startup_settings()


def test_no_token_and_no_dev_mode_is_refused(monkeypatch):
    _configure(monkeypatch, dev_mode=False, token="")
    with pytest.raises(RuntimeError, match="BOT_TOKEN"):
        check_startup_settings()


def test_production_config_is_ok(monkeypatch):
    _configure(monkeypatch, dev_mode=False, token="123456:TOKEN")
    check_startup_settings()


def test_local_dev_config_is_ok(monkeypatch):
    _configure(monkeypatch, dev_mode=True, token="")
    check_startup_settings()


def test_refusal_does_not_leak_the_token(monkeypatch, caplog):
    secret = "123456:SUPER_SECRET_TOKEN_VALUE"
    _configure(monkeypatch, dev_mode=True, token=secret)
    with caplog.at_level("CRITICAL"), pytest.raises(RuntimeError) as exc:
        check_startup_settings()
    assert secret not in caplog.text
    assert secret not in str(exc.value)


def test_app_does_not_start_with_dev_mode_and_token(monkeypatch):
    # через настоящий lifespan: приложение не должно подняться (и не должно трогать базу)
    _configure(monkeypatch, dev_mode=True, token="123456:TOKEN")
    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass
