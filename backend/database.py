"""Движок SQLAlchemy, сессии, базовый класс моделей и инициализация БД."""
from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


class Base(DeclarativeBase):
    """Базовый класс всех ORM-моделей."""


engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    # Без этого CASCADE и SET NULL в SQLite не работают
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=True)


def utcnow() -> datetime:
    """Текущее время в UTC."""
    return datetime.now(timezone.utc)


def get_db() -> Generator[Session, None, None]:
    """Зависимость FastAPI: сессия БД на время запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_columns() -> None:
    """Добавляет колонки, появившиеся после первого релиза (миграций в проекте нет)."""
    with engine.begin() as conn:
        columns = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(products)")}
        if "owner_user_id" not in columns:
            conn.exec_driver_sql(
                "ALTER TABLE products ADD COLUMN owner_user_id INTEGER "
                "REFERENCES users(id) ON DELETE CASCADE"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_products_owner_user_id "
                "ON products (owner_user_id)"
            )


def init_db() -> None:
    """Создаёт таблицы и загружает стартовые продукты."""
    import models  # noqa: F401  (регистрирует модели в Base.metadata)
    from services import product_service

    Base.metadata.create_all(engine)
    _ensure_columns()
    with SessionLocal() as db:
        product_service.seed_local_products(db)
