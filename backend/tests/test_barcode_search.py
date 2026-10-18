"""Поиск по штрихкоду: продукты из импорта (off-<код>, st-<код>) находятся без сети."""
from services import openfoodfacts, product_service
from services.errors import ExternalServiceError


def _fail_if_network(monkeypatch):
    """Любое обращение к OpenFoodFacts в этих тестах — ошибка."""

    def _boom(*args, **kwargs):
        raise AssertionError("не должно быть запроса к OpenFoodFacts")

    monkeypatch.setattr(openfoodfacts, "get_product", _boom)
    monkeypatch.setattr(openfoodfacts, "search_products", _boom)


def test_imported_product_is_found_by_barcode(db, make_product, monkeypatch):
    _fail_if_network(monkeypatch)
    imported = make_product(code="off-4600000000017", name="Импортный сыр", name_search="импортный сыр")
    result = product_service.search(db, "4600000000017")
    assert [p.id for p in result.items] == [imported.id]
    assert result.external_status == "skipped"


def test_store_product_is_found_by_barcode(db, make_product, monkeypatch):
    _fail_if_network(monkeypatch)
    store = make_product(code="st-4601234567890", name="Из магазина", name_search="из магазина")
    assert [p.id for p in product_service.search(db, "4601234567890").items] == [store.id]


def test_barcode_with_leading_zeros(db, make_product, monkeypatch):
    _fail_if_network(monkeypatch)
    imported = make_product(code="off-00051122", name="Хлеб", name_search="хлеб")
    assert [p.id for p in product_service.search(db, "00051122").items] == [imported.id]


def test_exact_code_wins_over_prefixed(db, make_product, monkeypatch):
    _fail_if_network(monkeypatch)
    cached = make_product(code="4600000000017", name="Кэш OFF", name_search="кэш off", source="off")
    make_product(code="off-4600000000017", name="Импорт", name_search="импорт")
    # у кэша OFF source='off', но он свежий — запрос к сети не нужен
    from database import utcnow

    cached.cached_at = utcnow()
    db.commit()
    assert product_service.search(db, "4600000000017").items[0].id == cached.id


def test_unknown_barcode_asks_openfoodfacts_and_survives_failure(db):
    # автоматическая заглушка no_network: OFF недоступен -> пустой результат, а не ошибка
    result = product_service.search(db, "4609999999999")
    assert result.items == []
    assert result.external_status == "unavailable"


def test_other_users_product_codes_are_not_barcodes(db, make_product, monkeypatch):
    _fail_if_network(monkeypatch)
    make_product(code="u-4600000000017", name="Чужой", name_search="чужой", source="user")
    # код вида u-<цифры> не должен находиться по штрихкоду: поиск идёт среди OFF/магазинов
    monkeypatch.setattr(openfoodfacts, "get_product", lambda code: (_ for _ in ()).throw(ExternalServiceError("нет сети")))
    assert product_service.search(db, "4600000000017").items == []


def test_api_barcode_search_finds_imported_product(client, make_product):
    from tests.conftest import auth_headers

    make_product(code="off-4600000000017", name="Импортное молоко", name_search="импортное молоко")
    response = client.get("/api/products/search?q=4600000000017", headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert [p["name"] for p in body["items"]] == ["Импортное молоко"]
    assert body["external_status"] == "skipped"
