"""API через TestClient: авторизация и основные сценарии."""
import datetime as dt
import time

from tests.conftest import auth_headers, make_init_data

TODAY = dt.datetime.now(dt.timezone.utc).date().isoformat()


def test_health_needs_no_auth(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_no_authorization_is_401(client):
    for path in ("/api/user/settings", f"/api/diary/day?date={TODAY}", "/api/products/search?q=сыр"):
        response = client.get(path)
        assert response.status_code == 401, path
        assert response.json() == {"detail": "Откройте приложение через Telegram"}


def test_valid_init_data_is_200_and_creates_user(client):
    response = client.get("/api/user/settings", headers=auth_headers(777, "Мария"))
    assert response.status_code == 200
    body = response.json()
    assert body["telegram_id"] == 777
    assert body["first_name"] == "Мария"
    assert (body["daily_calories"], body["daily_protein"], body["daily_fat"], body["daily_carbs"]) == (2000, 100, 67, 250)


def test_tampered_init_data_is_401(client):
    headers = {"Authorization": "tma " + make_init_data(tamper=True)}
    assert client.get("/api/user/settings", headers=headers).status_code == 401


def test_expired_init_data_is_401(client):
    old = make_init_data(auth_date=int(time.time()) - 3 * 86400)
    assert client.get("/api/user/settings", headers={"Authorization": "tma " + old}).status_code == 401


def test_wrong_scheme_is_401(client):
    init_data = make_init_data()
    assert client.get("/api/user/settings", headers={"Authorization": "Bearer " + init_data}).status_code == 401


def test_user_id_from_query_is_ignored(client):
    # Пользователь определяется только подписью, не параметрами запроса
    response = client.get("/api/user/settings?telegram_id=1", headers=auth_headers(555))
    assert response.json()["telegram_id"] == 555


def test_settings_update_and_validation(client):
    headers = auth_headers()
    ok = {"daily_calories": 1800, "daily_protein": 120, "daily_fat": 60, "daily_carbs": 180}
    assert client.put("/api/user/settings", json=ok, headers=headers).json()["daily_calories"] == 1800
    bad = client.put("/api/user/settings", json={**ok, "daily_calories": 100}, headers=headers)
    assert bad.status_code == 422
    assert bad.json()["detail"].startswith("Некорректные данные")


def test_create_product_and_isolation_between_users(client):
    alice, bob = auth_headers(1, "Alice"), auth_headers(2, "Bob")
    payload = {"name": "Мой сырник", "calories": 220, "protein": 14, "fat": 9, "carbs": 20}

    created = client.post("/api/products", json=payload, headers=alice)
    assert created.status_code == 201
    product = created.json()
    assert product["source"] == "user"

    found = client.get("/api/products/search?q=сырник", headers=alice).json()
    assert [p["id"] for p in found["items"]] == [product["id"]]
    assert client.get("/api/products/search?q=сырник", headers=bob).json()["items"] == []
    assert client.get(f"/api/products/{product['id']}", headers=bob).status_code == 404
    assert client.delete(f"/api/products/{product['id']}", headers=bob).status_code == 404
    assert client.delete(f"/api/products/{product['id']}", headers=alice).status_code == 204


def test_create_product_macros_sum_over_100_is_422(client):
    payload = {"name": "Невозможный", "calories": 500, "protein": 50, "fat": 50, "carbs": 50}
    response = client.post("/api/products", json=payload, headers=auth_headers())
    assert response.status_code == 422
    assert "100 г" in response.json()["detail"]


def test_diary_add_get_delete_flow(client, db, make_product):
    product = make_product()
    headers = auth_headers(10)
    body = {"product_id": product.id, "weight_g": 180, "meal_type": "breakfast", "entry_date": TODAY}

    added = client.post("/api/diary/add", json=body, headers=headers)
    assert added.status_code == 201
    entry = added.json()
    assert entry["calories"] == 217.8
    assert entry["created_at"].endswith("Z")

    day = client.get(f"/api/diary/day?date={TODAY}", headers=headers).json()
    assert day["totals"]["calories"] == 217.8
    assert len(day["meals"]["breakfast"]) == 1

    # чужой пользователь не может удалить запись
    assert client.delete(f"/api/diary/{entry['id']}", headers=auth_headers(11)).status_code == 404
    assert client.delete(f"/api/diary/{entry['id']}", headers=headers).status_code == 204
    assert client.get(f"/api/diary/day?date={TODAY}", headers=headers).json()["totals"]["calories"] == 0


def test_diary_validation_errors(client, make_product):
    product = make_product()
    headers = auth_headers()
    base = {"product_id": product.id, "weight_g": 100, "meal_type": "lunch", "entry_date": TODAY}
    assert client.post("/api/diary/add", json={**base, "weight_g": 0.5}, headers=headers).status_code == 422
    assert client.post("/api/diary/add", json={**base, "weight_g": 6000}, headers=headers).status_code == 422
    assert client.post("/api/diary/add", json={**base, "meal_type": "brunch"}, headers=headers).status_code == 422
    assert client.post("/api/diary/add", json={**base, "entry_date": "2000-01-01"}, headers=headers).status_code == 422
    assert client.post("/api/diary/add", json={**base, "product_id": 9999}, headers=headers).status_code == 404


def test_stats_endpoint(client, make_product):
    product = make_product()
    headers = auth_headers(20)
    client.post("/api/diary/add", json={"product_id": product.id, "weight_g": 100, "meal_type": "lunch", "entry_date": TODAY}, headers=headers)
    start = (dt.date.fromisoformat(TODAY) - dt.timedelta(days=6)).isoformat()
    stats = client.get(f"/api/stats?start_date={start}&end_date={TODAY}", headers=headers)
    assert stats.status_code == 200
    assert len(stats.json()["days"]) == 7
    assert stats.json()["days_logged"] == 1
    too_long = (dt.date.fromisoformat(TODAY) - dt.timedelta(days=40)).isoformat()
    assert client.get(f"/api/stats?start_date={too_long}&end_date={TODAY}", headers=headers).status_code == 422


def test_search_short_query_is_422(client):
    response = client.get("/api/products/search?q=a", headers=auth_headers())
    assert response.status_code == 422
    assert response.json()["detail"].startswith("Некорректные данные")
