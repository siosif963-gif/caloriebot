"""Свои продукты: валидация КБЖУ, видимость и удаление."""
import datetime as dt

import pydantic
import pytest

from schemas.product import ProductCreate
from services import diary_service, product_service
from services.errors import NotFoundError, ValidationError

BASE = {"name": "Домашний батончик", "brand": None, "calories": 400, "protein": 10, "fat": 10, "carbs": 50}


# ---------- валидация ----------

def test_macros_sum_over_100_is_rejected():
    with pytest.raises(pydantic.ValidationError):
        ProductCreate(**{**BASE, "protein": 50, "fat": 50, "carbs": 50})


def test_macros_sum_exactly_100_is_allowed():
    product = ProductCreate(**{**BASE, "protein": 40, "fat": 30, "carbs": 30, "calories": 550})
    assert product.protein + product.fat + product.carbs == 100


def test_pure_fat_is_allowed_up_to_900_kcal():
    ProductCreate(**{**BASE, "protein": 0, "fat": 100, "carbs": 0, "calories": 900})


@pytest.mark.parametrize(
    "patch",
    [
        {"calories": 901},
        {"calories": -1},
        {"protein": 101},
        {"name": "a"},
        {"name": ""},
    ],
)
def test_other_invalid_values(patch):
    with pytest.raises(pydantic.ValidationError):
        ProductCreate(**{**BASE, **patch})


def test_name_and_brand_are_normalized():
    product = ProductCreate(**{**BASE, "name": "  Мой   сырник ", "brand": "   "})
    assert product.name == "Мой сырник"
    assert product.brand is None


# ---------- видимость и права ----------

def _create(db, user, name="Мой сырник"):
    return product_service.create_user_product(db, user.id, name, None, 220, 14, 9, 20)


def test_user_product_is_visible_only_to_author(db, make_user):
    author, other = make_user(1), make_user(2)
    product = _create(db, author)

    mine = product_service.search(db, "сырник", author.id).items
    assert [p.id for p in mine] == [product.id]
    assert mine[0].source == "user"
    assert product_service.search(db, "сырник", other.id).items == []
    assert product_service.search(db, "сырник", None).items == []

    assert product_service.get_by_id(db, product.id, author.id).id == product.id
    with pytest.raises(NotFoundError):
        product_service.get_by_id(db, product.id, other.id)


def test_other_user_cannot_add_my_product_to_diary(db, make_user):
    author, other = make_user(1), make_user(2)
    product = _create(db, author)
    with pytest.raises(NotFoundError):
        diary_service.add_entry(db, other, product.id, 100, "lunch", dt.date(2026, 10, 12))


def test_other_user_cannot_delete_my_product(db, make_user):
    author, other = make_user(1), make_user(2)
    product = _create(db, author)
    with pytest.raises(NotFoundError):
        product_service.delete_user_product(db, other.id, product.id)
    # продукт на месте
    assert product_service.get_by_id(db, product.id, author.id).id == product.id


def test_cannot_delete_shared_product_via_user_endpoint(db, make_user, make_product):
    user = make_user(1)
    shared = make_product()
    with pytest.raises(NotFoundError):
        product_service.delete_user_product(db, user.id, shared.id)


def test_author_deletes_product_diary_history_is_kept(db, make_user):
    author = make_user(1)
    product = _create(db, author)
    day = dt.date(2026, 10, 12)
    entry = diary_service.add_entry(db, author, product.id, 200, "lunch", day)

    product_service.delete_user_product(db, author.id, product.id)

    db.refresh(entry)
    assert entry.product_id is None  # ON DELETE SET NULL
    assert entry.product_name == "Мой сырник"
    assert entry.calories == 440.0
    assert diary_service.get_day(db, author, day)["totals"]["calories"] == 440.0


def test_user_product_limit(db, make_user, monkeypatch):
    author = make_user(1)
    monkeypatch.setattr(product_service, "MAX_USER_PRODUCTS", 2)
    _create(db, author, "Первый")
    _create(db, author, "Второй")
    with pytest.raises(ValidationError):
        _create(db, author, "Третий")


def test_search_prefers_own_products(db, make_user, make_product):
    author = make_user(1)
    make_product(code="t-shared", name="Сырник общий", name_search="сырник общий", brand=None)
    mine = _create(db, author, "Сырник мой")
    items = product_service.search(db, "сырник", author.id).items
    assert items[0].id == mine.id
