"""Слияние локальной выдачи с результатами OpenFoodFacts без дублей."""
from services import openfoodfacts, product_service


def _off(code, name, brand=None, calories=100.0):
    """Распарсенный продукт OpenFoodFacts в том виде, в каком его отдаёт search_products."""
    return {"code": code, "name": name, "brand": brand, "calories": calories,
            "protein": 1.0, "fat": 1.0, "carbs": 10.0, "image_url": None}


def _names(result):
    return [p.name for p in result.items]


def test_live_result_duplicating_imported_product_is_not_repeated(db, make_product, monkeypatch):
    imported = make_product(code="off-4600000000017", name="Нутелла", name_search="нутелла")
    monkeypatch.setattr(
        openfoodfacts, "search_products",
        lambda q: [_off("4600000000017", "Нутелла"), _off("4600000000024", "Нутелла мини")],
    )
    result = product_service.search(db, "нутелла")
    assert _names(result) == ["Нутелла", "Нутелла мини"]
    assert result.items[0].id == imported.id  # остаётся локальный, а не живой дубль
    assert result.external_status == "ok"


def test_same_barcode_with_different_name_is_still_a_duplicate(db, make_product, monkeypatch):
    make_product(code="off-4600000000017", name="Нутелла", name_search="нутелла")
    monkeypatch.setattr(
        openfoodfacts, "search_products",
        lambda q: [_off("4600000000017", "Nutella Ferrero 350g")],
    )
    assert _names(product_service.search(db, "нутелла")) == ["Нутелла"]


def test_duplicates_inside_openfoodfacts_response(db, monkeypatch):
    monkeypatch.setattr(
        openfoodfacts, "search_products",
        lambda q: [_off("4600000000017", "Йогурт"), _off("4600000000024", "Йогурт"), _off("4600000000031", "Йогурт клубничный")],
    )
    assert _names(product_service.search(db, "йогурт")) == ["Йогурт", "Йогурт клубничный"]


def test_cached_query_path_has_no_duplicates(db, make_product):
    imported = make_product(code="off-4600000000017", name="Нутелла", name_search="нутелла")
    live = make_product(code="4600000000017", name="Нутелла", name_search="нутелла", source="off")
    openfoodfacts.cache_put("нутелла", [live.code])
    result = product_service.search(db, "нутелла")
    assert [p.id for p in result.items] == [imported.id]
    assert result.external_status == "skipped"


def test_different_products_with_similar_names_are_kept(db, make_product, monkeypatch):
    make_product(code="ru-1", name="Молоко 2.5%", name_search="молоко 2.5% простоквашино", brand="Простоквашино")
    monkeypatch.setattr(
        openfoodfacts, "search_products",
        lambda q: [_off("4600000000017", "Молоко 2.5%", "Домик в деревне")],
    )
    result = product_service.search(db, "молоко")
    assert len(result.items) == 2  # разные бренды — разные продукты


def test_merge_keeps_user_products_first(db, make_user, make_product, monkeypatch):
    user = make_user()
    mine = product_service.create_user_product(db, user.id, "Сырок мой", None, 300, 10, 10, 30)
    make_product(code="ru-9", name="Сырок", name_search="сырок")
    monkeypatch.setattr(openfoodfacts, "search_products", lambda q: [_off("4600000000017", "Сырок глазированный")])
    items = product_service.search(db, "сырок", user.id).items
    assert items[0].id == mine.id
    assert [p.source for p in items][:2] == ["user", "local"]
