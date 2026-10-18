"""Общие фикстуры. У каждого теста своя временная SQLite-база."""
import os
import tempfile

# Настройки читаются при импорте config, поэтому задаём окружение до любых импортов приложения.
# Рабочую базу и реальный токен тесты не трогают.
_TMP_DIR = tempfile.mkdtemp(prefix="caloriebot-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/unused-global.db"
os.environ["BOT_TOKEN"] = "123456:TEST_TOKEN_FOR_PYTEST"
os.environ["DEV_MODE"] = "false"
os.environ["FRONTEND_ORIGINS"] = ""
os.environ["LOG_LEVEL"] = "WARNING"

import hashlib  # noqa: E402
import hmac  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
import urllib.parse  # noqa: E402
from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

import models  # noqa: E402,F401  (регистрирует таблицы)
from config import settings  # noqa: E402
from database import Base, get_db  # noqa: E402
from main import app  # noqa: E402
from models.product import Product  # noqa: E402
from models.user import User  # noqa: E402
from services import openfoodfacts  # noqa: E402
from services.errors import ExternalServiceError  # noqa: E402

TEST_BOT_TOKEN = os.environ["BOT_TOKEN"]


def make_init_data(
    user: dict | None = None,
    *,
    bot_token: str = TEST_BOT_TOKEN,
    auth_date: int | None = None,
    include_hash: bool = True,
    include_user: bool = True,
    tamper: bool = False,
) -> str:
    """Собирает подписанную строку initData так же, как это делает Telegram."""
    fields: dict[str, str] = {
        "auth_date": str(int(time.time()) if auth_date is None else auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
    }
    if include_user:
        fields["user"] = json.dumps(
            user or {"id": 1001, "first_name": "Иван", "username": "ivan"},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if include_hash:
        fields["hash"] = signature
    if tamper:
        fields["query_id"] = "TAMPERED"  # подпись считалась по другим данным
    return urllib.parse.urlencode(fields)


@pytest.fixture
def engine(tmp_path):
    """Отдельная SQLite-база на каждый тест, с включёнными внешними ключами."""
    eng = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=True)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """OpenFoodFacts в тестах всегда «недоступен»: сети нет, кэш запросов чистый."""

    def _unavailable(*args, **kwargs):
        raise ExternalServiceError("сеть отключена в тестах")

    monkeypatch.setattr(openfoodfacts, "search_products", _unavailable)
    monkeypatch.setattr(openfoodfacts, "get_product", _unavailable)
    openfoodfacts._query_cache.clear()


@pytest.fixture
def client(engine, monkeypatch) -> Generator[TestClient, None, None]:
    """Клиент API на временной базе. Без контекстного менеджера: lifespan и сидинг не нужны."""
    monkeypatch.setattr(settings, "BOT_TOKEN", TEST_BOT_TOKEN)
    monkeypatch.setattr(settings, "DEV_MODE", False)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=True)

    def _get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def make_user(db):
    def _make(telegram_id: int = 1001, **kwargs) -> User:
        user = User(telegram_id=telegram_id, first_name=kwargs.pop("first_name", "Тест"), **kwargs)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def make_product(db):
    def _make(**kwargs) -> Product:
        data = {
            "code": f"t-{kwargs.get('name', 'x')}",
            "name": "Творог 5%",
            "brand": "ВкусВилл",
            "name_search": "творог 5% вкусвилл",
            "calories": 121.0,
            "protein": 17.0,
            "fat": 5.0,
            "carbs": 1.8,
            "source": "local",
        }
        data.update(kwargs)
        product = Product(**data)
        db.add(product)
        db.commit()
        db.refresh(product)
        return product

    return _make


def auth_headers(telegram_id: int = 1001, first_name: str = "Иван") -> dict[str, str]:
    init_data = make_init_data({"id": telegram_id, "first_name": first_name})
    return {"Authorization": f"tma {init_data}"}
