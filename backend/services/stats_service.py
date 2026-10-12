"""Статистика питания за период."""
import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.diary_entry import DiaryEntry
from models.user import User
from services.errors import ValidationError

MAX_PERIOD_DAYS = 31


def get_stats(db: Session, user: User, start_date: dt.date, end_date: dt.date) -> dict:
    """Суммы по каждому дню периода (включительно) и средние по дням с записями."""
    if end_date < start_date:
        raise ValidationError(
            "Некорректные данные: end_date — не может быть раньше start_date"
        )
    period_days = (end_date - start_date).days + 1
    if period_days > MAX_PERIOD_DAYS:
        raise ValidationError(
            "Некорректные данные: end_date — период не может быть длиннее 31 дня"
        )

    rows = db.execute(
        select(
            DiaryEntry.entry_date,
            func.count(DiaryEntry.id),
            func.sum(DiaryEntry.calories),
            func.sum(DiaryEntry.protein),
            func.sum(DiaryEntry.fat),
            func.sum(DiaryEntry.carbs),
        )
        .where(
            DiaryEntry.user_id == user.id,
            DiaryEntry.entry_date >= start_date,
            DiaryEntry.entry_date <= end_date,
        )
        .group_by(DiaryEntry.entry_date)
    ).all()

    by_date = {
        row[0]: {
            "calories": row[2] or 0.0,
            "protein": row[3] or 0.0,
            "fat": row[4] or 0.0,
            "carbs": row[5] or 0.0,
        }
        for row in rows
    }

    days: list[dict] = []
    for offset in range(period_days):
        day = start_date + dt.timedelta(days=offset)
        values = by_date.get(day, {"calories": 0.0, "protein": 0.0, "fat": 0.0, "carbs": 0.0})
        days.append({"date": day, **{k: round(v, 1) for k, v in values.items()}})

    days_logged = len(by_date)
    if days_logged:
        averages = {
            key: round(sum(v[key] for v in by_date.values()) / days_logged, 1)
            for key in ("calories", "protein", "fat", "carbs")
        }
    else:
        averages = {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}

    return {
        "start_date": start_date,
        "end_date": end_date,
        "days": days,
        "averages": averages,
        "days_logged": days_logged,
        "goal_calories": user.daily_calories,
    }
