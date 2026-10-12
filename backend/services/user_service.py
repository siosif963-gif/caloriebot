"""Работа с пользователями."""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.user import User


def _find_by_telegram_id(db: Session, telegram_id: int) -> User | None:
    return db.scalar(select(User).where(User.telegram_id == telegram_id))


def get_or_create_user(
    db: Session, telegram_id: int, first_name: str, username: str | None
) -> User:
    """Возвращает пользователя, создавая его с нормами по умолчанию при первом входе."""
    user = _find_by_telegram_id(db, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id, first_name=first_name, username=username)
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            # Параллельный первый запрос уже создал пользователя
            db.rollback()
            user = _find_by_telegram_id(db, telegram_id)
            if user is None:
                raise
        return user

    if user.first_name != first_name or user.username != username:
        user.first_name = first_name
        user.username = username
        db.commit()
    return user


def update_settings(db: Session, user: User, values: dict[str, int]) -> User:
    """Обновляет дневные нормы пользователя."""
    user.daily_calories = values["daily_calories"]
    user.daily_protein = values["daily_protein"]
    user.daily_fat = values["daily_fat"]
    user.daily_carbs = values["daily_carbs"]
    db.commit()
    db.refresh(user)
    return user
