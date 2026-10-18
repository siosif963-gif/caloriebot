"""Статистика за неделю и месяц."""
import datetime as dt

import pytest

from services import diary_service, stats_service
from services.errors import ValidationError

END = dt.date(2026, 10, 30)


@pytest.fixture
def prepared(db, make_user, make_product):
    """Три дня с записями внутри месяца; один день — вне недели."""
    user = make_user(daily_calories=2000)
    product = make_product(calories=100, protein=10, fat=5, carbs=20)
    for days_ago, weight in [(0, 100), (2, 300), (3, 200), (20, 400)]:
        diary_service.add_entry(
            db, user, product.id, weight, "lunch", END - dt.timedelta(days=days_ago)
        )
    return user


def test_week_has_every_day_and_zero_fill(db, prepared):
    stats = stats_service.get_stats(db, prepared, END - dt.timedelta(days=6), END)
    assert len(stats["days"]) == 7
    assert [d["date"] for d in stats["days"]] == [END - dt.timedelta(days=6 - i) for i in range(7)]
    by_date = {d["date"]: d for d in stats["days"]}
    assert by_date[END]["calories"] == 100.0
    assert by_date[END - dt.timedelta(days=1)]["calories"] == 0  # день без записей — нули
    assert by_date[END - dt.timedelta(days=2)]["calories"] == 300.0
    assert stats["days_logged"] == 3
    assert stats["goal_calories"] == 2000


def test_week_averages_are_over_logged_days_only(db, prepared):
    stats = stats_service.get_stats(db, prepared, END - dt.timedelta(days=6), END)
    # (100 + 300 + 200) / 3 = 200 ккал, а не деление на 7
    assert stats["averages"]["calories"] == 200.0
    assert stats["averages"]["protein"] == 20.0
    assert stats["averages"]["fat"] == 10.0
    assert stats["averages"]["carbs"] == 40.0


def test_month_includes_older_entries(db, prepared):
    stats = stats_service.get_stats(db, prepared, END - dt.timedelta(days=29), END)
    assert len(stats["days"]) == 30
    assert stats["days_logged"] == 4
    assert stats["averages"]["calories"] == 250.0  # (100 + 300 + 200 + 400) / 4


def test_empty_period_has_zero_averages(db, make_user):
    user = make_user()
    stats = stats_service.get_stats(db, user, END - dt.timedelta(days=6), END)
    assert stats["days_logged"] == 0
    assert stats["averages"] == {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}
    assert len(stats["days"]) == 7


def test_other_users_data_is_not_counted(db, prepared, make_user, make_product):
    other = make_user(2)
    product = make_product(code="t-o", name="O", calories=900, protein=0, fat=100, carbs=0)
    diary_service.add_entry(db, other, product.id, 100, "lunch", END)
    stats = stats_service.get_stats(db, prepared, END - dt.timedelta(days=6), END)
    assert {d["date"]: d for d in stats["days"]}[END]["calories"] == 100.0


def test_period_limits(db, make_user):
    user = make_user()
    with pytest.raises(ValidationError):
        stats_service.get_stats(db, user, END, END - dt.timedelta(days=1))  # конец раньше начала
    with pytest.raises(ValidationError):
        stats_service.get_stats(db, user, END - dt.timedelta(days=31), END)  # 32 дня
    # ровно 31 день допустим
    assert len(stats_service.get_stats(db, user, END - dt.timedelta(days=30), END)["days"]) == 31
