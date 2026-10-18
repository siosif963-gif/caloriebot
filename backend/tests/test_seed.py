"""Синхронизация локальных продуктов с JSON-файлами (сидинг)."""
import datetime as dt
import json

import pytest
from sqlalchemy import func, select

from models.diary_entry import DiaryEntry
from models.product import Product
from services import diary_service, product_service


def _item(code, name, calories=100.0, **extra):
    return {"code": code, "name": name, "brand": None, "calories": calories,
            "protein": 5.0, "fat": 2.0, "carbs": 10.0, **extra}


MAIN = [_item("ru-0001", "Творог"), _item("ru-0002", "Кефир")]
OFF = [_item("off-111", "Импорт один"), _item("off-222", "Импорт два", image_url="https://x/y.jpg")]


@pytest.fixture
def seed_files(tmp_path, monkeypatch):
    main, off = tmp_path / "main.json", tmp_path / "off.json"
    main.write_text(json.dumps(MAIN), encoding="utf-8")
    off.write_text(json.dumps(OFF), encoding="utf-8")
    monkeypatch.setattr(product_service, "SEED_FILE", main)
    monkeypatch.setattr(product_service, "SEED_OFF_FILE", off)
    return main, off


def _codes(db):
    return set(db.scalars(select(Product.code)))


def test_initial_seed_loads_both_files(db, seed_files):
    product_service.seed_local_products(db)
    assert _codes(db) == {"ru-0001", "ru-0002", "off-111", "off-222"}
    imported = db.scalar(select(Product).where(Product.code == "off-222"))
    assert imported.source == "local" and imported.image_url == "https://x/y.jpg"


def test_seed_is_idempotent(db, seed_files):
    product_service.seed_local_products(db)
    product_service.seed_local_products(db)
    assert db.scalar(select(func.count()).select_from(Product)) == 4


def test_changed_values_are_updated(db, seed_files):
    product_service.seed_local_products(db)
    main, _ = seed_files
    main.write_text(json.dumps([_item("ru-0001", "Творог 9%", 169.0), MAIN[1]]), encoding="utf-8")
    product_service.seed_local_products(db)
    product = db.scalar(select(Product).where(Product.code == "ru-0001"))
    assert (product.name, product.calories) == ("Творог 9%", 169.0)
    assert "9%" in product.name_search


def test_removed_from_json_is_deleted_and_diary_keeps_snapshot(db, seed_files, make_user):
    product_service.seed_local_products(db)
    user = make_user()
    gone = db.scalar(select(Product).where(Product.code == "ru-0002"))
    entry = diary_service.add_entry(db, user, gone.id, 200, "lunch", dt.date(2026, 10, 12))

    main, _ = seed_files
    main.write_text(json.dumps([MAIN[0]]), encoding="utf-8")  # «Кефир» исчез из справочника
    product_service.seed_local_products(db)

    assert "ru-0002" not in _codes(db)
    db.refresh(entry)
    assert entry.product_id is None  # ON DELETE SET NULL
    assert (entry.product_name, entry.calories) == ("Кефир", 200.0)
    assert diary_service.get_day(db, user, dt.date(2026, 10, 12))["totals"]["calories"] == 200.0


def test_user_and_live_off_products_survive_pruning(db, seed_files, make_user, make_product):
    product_service.seed_local_products(db)
    user = make_user()
    mine = product_service.create_user_product(db, user.id, "Мой продукт", None, 100, 5, 5, 10)
    live = make_product(code="4600000000017", name="Живой", name_search="живой", source="off")
    main, off = seed_files
    main.write_text(json.dumps([MAIN[0]]), encoding="utf-8")
    off.write_text(json.dumps([OFF[0]]), encoding="utf-8")
    product_service.seed_local_products(db)
    assert {"ru-0002", "off-222"}.isdisjoint(_codes(db))
    assert db.get(Product, mine.id) is not None
    assert db.get(Product, live.id) is not None


def test_missing_off_file_keeps_imported_products(db, seed_files):
    product_service.seed_local_products(db)
    _, off = seed_files
    off.unlink()
    product_service.seed_local_products(db)
    assert {"off-111", "off-222"} <= _codes(db)
    assert {"ru-0001", "ru-0002"} <= _codes(db)


def test_missing_off_file_still_syncs_main(db, seed_files):
    product_service.seed_local_products(db)
    main, off = seed_files
    off.unlink()
    main.write_text(json.dumps([_item("ru-0001", "Творог"), _item("ru-0003", "Новый")]), encoding="utf-8")
    product_service.seed_local_products(db)
    assert "ru-0003" in _codes(db) and "ru-0002" not in _codes(db)
    assert {"off-111", "off-222"} <= _codes(db)


@pytest.mark.parametrize("bad_content", ["{не json", "[]", '{"a": 1}'])
def test_corrupt_or_empty_off_file_keeps_imported_products(db, seed_files, bad_content):
    product_service.seed_local_products(db)
    _, off = seed_files
    off.write_text(bad_content, encoding="utf-8")
    product_service.seed_local_products(db)
    assert {"off-111", "off-222"} <= _codes(db)


def test_missing_main_file_changes_nothing(db, seed_files):
    product_service.seed_local_products(db)
    main, _ = seed_files
    main.unlink()
    product_service.seed_local_products(db)
    assert _codes(db) == {"ru-0001", "ru-0002", "off-111", "off-222"}


@pytest.mark.parametrize("bad_content", ["{не json", "[]"])
def test_corrupt_main_file_changes_nothing(db, seed_files, bad_content):
    product_service.seed_local_products(db)
    main, _ = seed_files
    main.write_text(bad_content, encoding="utf-8")
    product_service.seed_local_products(db)
    assert _codes(db) == {"ru-0001", "ru-0002", "off-111", "off-222"}


def test_both_files_missing_changes_nothing(db, seed_files):
    product_service.seed_local_products(db)
    for path in seed_files:
        path.unlink()
    product_service.seed_local_products(db)
    assert len(_codes(db)) == 4
    assert db.scalar(select(func.count()).select_from(DiaryEntry)) == 0
