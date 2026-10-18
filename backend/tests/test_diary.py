"""Расчёт КБЖУ порции и итоги дня."""
import datetime as dt

import pytest

from services import diary_service
from services.errors import NotFoundError

DAY = dt.date(2026, 10, 12)


def test_portion_is_calculated_by_weight(db, make_user, make_product):
    user = make_user()
    product = make_product()  # 121 ккал, Б 17, Ж 5, У 1.8 на 100 г
    entry = diary_service.add_entry(db, user, product.id, 180, "breakfast", DAY)
    assert entry.calories == 217.8
    assert entry.protein == 30.6
    assert entry.fat == 9.0
    assert entry.carbs == 3.2  # 1.8 * 1.8 = 3.24 -> 3.2


def test_portion_rounding_to_one_decimal(db, make_user, make_product):
    user = make_user()
    product = make_product(calories=53.0, protein=3.0, fat=2.5, carbs=4.0, code="t-r")
    entry = diary_service.add_entry(db, user, product.id, 33.3, "lunch", DAY)
    assert entry.calories == round(53.0 * 33.3 / 100, 1)
    assert entry.fat == round(2.5 * 33.3 / 100, 1)


def test_entry_keeps_name_and_brand_snapshot(db, make_user, make_product):
    user = make_user()
    product = make_product()
    entry = diary_service.add_entry(db, user, product.id, 100, "snack", DAY)
    assert (entry.product_name, entry.product_brand) == ("Творог 5%", "ВкусВилл")
    # Переименование продукта не меняет уже сделанную запись
    product.name = "Другое название"
    db.commit()
    db.refresh(entry)
    assert entry.product_name == "Творог 5%"


def test_unknown_product(db, make_user):
    user = make_user()
    with pytest.raises(NotFoundError):
        diary_service.add_entry(db, user, 9999, 100, "lunch", DAY)


def test_day_totals_and_goals(db, make_user, make_product):
    user = make_user(daily_calories=1800)
    a = make_product(code="t-a", name="A", calories=100, protein=10, fat=1, carbs=5)
    b = make_product(code="t-b", name="B", calories=200, protein=2, fat=10, carbs=20)
    diary_service.add_entry(db, user, a.id, 100, "breakfast", DAY)
    diary_service.add_entry(db, user, b.id, 50, "breakfast", DAY)
    diary_service.add_entry(db, user, b.id, 100, "dinner", DAY)
    diary_service.add_entry(db, user, a.id, 100, "lunch", DAY + dt.timedelta(days=1))  # чужой день

    day = diary_service.get_day(db, user, DAY)
    assert set(day["meals"]) == {"breakfast", "lunch", "dinner", "snack"}
    assert len(day["meals"]["breakfast"]) == 2
    assert day["meals"]["lunch"] == []  # пустые приёмы пищи присутствуют всегда
    assert day["meal_totals"]["breakfast"]["calories"] == 200.0
    assert day["meal_totals"]["dinner"]["calories"] == 200.0
    assert day["totals"] == {"calories": 400.0, "protein": 13.0, "fat": 16.0, "carbs": 35.0}
    assert day["goals"]["calories"] == 1800


def test_other_users_entries_are_not_in_my_day(db, make_user, make_product):
    me, other = make_user(1), make_user(2)
    product = make_product()
    diary_service.add_entry(db, other, product.id, 100, "lunch", DAY)
    assert diary_service.get_day(db, me, DAY)["totals"]["calories"] == 0


def test_delete_entry_only_own(db, make_user, make_product):
    me, other = make_user(1), make_user(2)
    product = make_product()
    entry = diary_service.add_entry(db, me, product.id, 100, "lunch", DAY)
    with pytest.raises(NotFoundError):
        diary_service.delete_entry(db, other, entry.id)
    diary_service.delete_entry(db, me, entry.id)
    assert diary_service.get_day(db, me, DAY)["totals"]["calories"] == 0
