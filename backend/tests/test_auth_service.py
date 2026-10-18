"""Проверка подписи Telegram initData."""
import time

import pytest

from services.auth_service import validate_init_data
from services.errors import AuthError
from tests.conftest import TEST_BOT_TOKEN, make_init_data

MAX_AGE = 86400


def test_valid_signature_returns_user():
    init_data = make_init_data({"id": 42, "first_name": "Анна", "username": "anna"})
    user = validate_init_data(init_data, TEST_BOT_TOKEN, MAX_AGE)
    assert user == {"id": 42, "first_name": "Анна", "username": "anna"}


def test_wrong_signature_when_data_tampered():
    init_data = make_init_data(tamper=True)
    with pytest.raises(AuthError):
        validate_init_data(init_data, TEST_BOT_TOKEN, MAX_AGE)


def test_wrong_signature_when_other_bot_token():
    init_data = make_init_data(bot_token="999:OTHER_BOT")
    with pytest.raises(AuthError):
        validate_init_data(init_data, TEST_BOT_TOKEN, MAX_AGE)


def test_expired_auth_date():
    old = int(time.time()) - MAX_AGE - 60
    init_data = make_init_data(auth_date=old)
    with pytest.raises(AuthError):
        validate_init_data(init_data, TEST_BOT_TOKEN, MAX_AGE)


def test_auth_date_inside_window_is_accepted():
    recent = int(time.time()) - MAX_AGE + 120
    init_data = make_init_data(auth_date=recent)
    assert validate_init_data(init_data, TEST_BOT_TOKEN, MAX_AGE)["id"] == 1001


def test_missing_hash():
    init_data = make_init_data(include_hash=False)
    with pytest.raises(AuthError):
        validate_init_data(init_data, TEST_BOT_TOKEN, MAX_AGE)


def test_missing_user_field():
    init_data = make_init_data(include_user=False)
    with pytest.raises(AuthError):
        validate_init_data(init_data, TEST_BOT_TOKEN, MAX_AGE)


@pytest.mark.parametrize("garbage", ["", "not-a-query-string", "hash=abc", "&&&"])
def test_garbage_input(garbage):
    with pytest.raises(AuthError):
        validate_init_data(garbage, TEST_BOT_TOKEN, MAX_AGE)


def test_empty_bot_token_is_rejected():
    init_data = make_init_data()
    with pytest.raises(AuthError):
        validate_init_data(init_data, "", MAX_AGE)
