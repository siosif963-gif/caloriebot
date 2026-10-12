"""Общие зависимости роутеров: текущий пользователь по initData."""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.user import User
from services import auth_service, user_service
from services.errors import AuthError

AUTH_REQUIRED_MESSAGE = "Откройте приложение через Telegram"


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Определяет пользователя только по подписанной строке initData."""
    if not authorization:
        if settings.DEV_MODE:
            return user_service.get_or_create_user(
                db, settings.DEV_USER_ID, "Dev", None
            )
        raise HTTPException(status_code=401, detail=AUTH_REQUIRED_MESSAGE)

    if not authorization.startswith("tma "):
        raise HTTPException(status_code=401, detail=AUTH_REQUIRED_MESSAGE)

    try:
        data = auth_service.validate_init_data(
            authorization[4:], settings.BOT_TOKEN, settings.INIT_DATA_MAX_AGE
        )
    except AuthError:
        raise HTTPException(status_code=401, detail=AUTH_REQUIRED_MESSAGE) from None

    return user_service.get_or_create_user(
        db,
        telegram_id=data["id"],
        first_name=str(data.get("first_name") or ""),
        username=data.get("username"),
    )
