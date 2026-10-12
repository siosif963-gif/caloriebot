"""Дневник питания: добавление, чтение за день, удаление."""
import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import utcnow
from models.diary_entry import DiaryEntry
from models.product import Product
from models.user import User
from services.errors import NotFoundError

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snack")
MACRO_KEYS = ("calories", "protein", "fat", "carbs")


def add_entry(
    db: Session,
    user: User,
    product_id: int,
    weight_g: float,
    meal_type: str,
    entry_date: dt.date,
) -> DiaryEntry:
    """Считает КБЖУ порции и сохраняет запись со снимком названия и бренда."""
    product = db.get(Product, product_id)
    if product is None or (
        product.owner_user_id is not None and product.owner_user_id != user.id
    ):
        raise NotFoundError("Продукт не найден")

    entry = DiaryEntry(
        user_id=user.id,
        product_id=product.id,
        product_name=product.name,
        product_brand=product.brand,
        meal_type=meal_type,
        weight_g=weight_g,
        calories=round(product.calories * weight_g / 100, 1),
        protein=round(product.protein * weight_g / 100, 1),
        fat=round(product.fat * weight_g / 100, 1),
        carbs=round(product.carbs * weight_g / 100, 1),
        entry_date=entry_date,
        created_at=utcnow(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_day(db: Session, user: User, day: dt.date) -> dict:
    """Записи дня по приёмам пищи, итоги по приёмам и за день, нормы пользователя."""
    entries = db.scalars(
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user.id, DiaryEntry.entry_date == day)
        .order_by(DiaryEntry.created_at, DiaryEntry.id)
    )

    meals: dict[str, list[DiaryEntry]] = {m: [] for m in MEAL_TYPES}
    meal_totals = {m: dict.fromkeys(MACRO_KEYS, 0.0) for m in MEAL_TYPES}
    totals = dict.fromkeys(MACRO_KEYS, 0.0)

    for entry in entries:
        meal = entry.meal_type if entry.meal_type in meals else "snack"
        meals[meal].append(entry)
        for key in MACRO_KEYS:
            value = getattr(entry, key)
            meal_totals[meal][key] += value
            totals[key] += value

    return {
        "date": day,
        "meals": meals,
        "meal_totals": {
            m: {k: round(v, 1) for k, v in values.items()}
            for m, values in meal_totals.items()
        },
        "totals": {k: round(v, 1) for k, v in totals.items()},
        "goals": {
            "calories": user.daily_calories,
            "protein": user.daily_protein,
            "fat": user.daily_fat,
            "carbs": user.daily_carbs,
        },
    }


def delete_entry(db: Session, user: User, entry_id: int) -> None:
    """Удаляет запись только текущего пользователя; чужая и несуществующая — одно и то же."""
    entry = db.scalar(
        select(DiaryEntry).where(
            DiaryEntry.id == entry_id, DiaryEntry.user_id == user.id
        )
    )
    if entry is None:
        raise NotFoundError("Запись не найдена")
    db.delete(entry)
    db.commit()
