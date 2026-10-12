"""Проверка подписи Telegram initData (чистая функция, без FastAPI)."""
import hashlib
import hmac
import json
import time
import urllib.parse

from services.errors import AuthError


def validate_init_data(init_data: str, bot_token: str, max_age_seconds: int) -> dict:
    """Проверяет подпись initData и возвращает данные пользователя (dict)."""
    if not init_data or not bot_token:
        raise AuthError("Откройте приложение через Telegram")

    try:
        pairs = dict(
            urllib.parse.parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
        )
    except ValueError as exc:
        raise AuthError("Некорректный initData") from exc

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise AuthError("В initData нет подписи")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise AuthError("Неверная подпись initData")

    try:
        auth_date = int(pairs["auth_date"])
    except (KeyError, ValueError) as exc:
        raise AuthError("В initData нет корректной auth_date") from exc
    if time.time() - auth_date > max_age_seconds:
        raise AuthError("initData устарел")

    raw_user = pairs.get("user")
    if not raw_user:
        raise AuthError("В initData нет пользователя")
    try:
        user = json.loads(raw_user)
    except ValueError as exc:
        raise AuthError("Некорректные данные пользователя") from exc
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise AuthError("Некорректные данные пользователя")
    return user
