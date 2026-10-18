"""Продукты: нормализация, умный поиск, кэш OpenFoodFacts, сидинг."""
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from database import utcnow
from models.product import Product
from services import openfoodfacts
from services.errors import ExternalServiceError, NotFoundError, ValidationError

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEED_FILE = DATA_DIR / "russian_products.json"
# Выгрузка OpenFoodFacts (русскоязычные продукты с КБЖУ), коды вида off-<штрихкод>
SEED_OFF_FILE = DATA_DIR / "off_ru_products.json"
MAX_RESULTS = 20
MIN_LOCAL_RESULTS = 5
MAX_USER_PRODUCTS = 300


@dataclass
class SearchResult:
    items: list[Product]
    external_status: str  # ok | skipped | unavailable


def normalize_name(*parts: str | None) -> str:
    """Нормализует строку для поиска: нижний регистр, ё -> е, без пунктуации."""
    text = " ".join(p for p in parts if p)
    text = text.lower().replace("ё", "е")
    text = re.sub(r"[^\w\s%]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _escape_like(word: str) -> str:
    return word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _is_stale(product: Product) -> bool:
    """Продукт off старше OFF_CACHE_TTL_DAYS (или без cached_at) считается устаревшим."""
    if product.source != "off":
        return False
    cached_at = product.cached_at
    if cached_at is None:
        return True
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=timezone.utc)
    return utcnow() - cached_at > timedelta(days=settings.OFF_CACHE_TTL_DAYS)


def _apply_data(product: Product, data: dict) -> None:
    product.name = data["name"]
    product.brand = data["brand"]
    product.name_search = normalize_name(data["name"], data["brand"])[:512]
    product.calories = data["calories"]
    product.protein = data["protein"]
    product.fat = data["fat"]
    product.carbs = data["carbs"]
    product.image_url = data["image_url"]


def _new_off_product(data: dict) -> Product:
    product = Product(code=data["code"], source="off", cached_at=utcnow())
    _apply_data(product, data)
    return product


def _refresh_if_stale(db: Session, product: Product) -> Product:
    """Обновляет устаревший продукт off; при любой ошибке отдаёт старые данные."""
    if not _is_stale(product):
        return product
    try:
        data = openfoodfacts.get_product(product.code)
    except ExternalServiceError as exc:
        logger.warning("Не удалось обновить продукт %s: %s", product.code, exc.message)
        return product
    if data is None:
        logger.warning("Продукт %s пропал из OpenFoodFacts", product.code)
        return product
    _apply_data(product, data)
    product.cached_at = utcnow()
    db.commit()
    return product


def _search_local(
    db: Session, words: list[str], user_id: int | None = None
) -> list[Product]:
    if not words:
        return []
    # Чужие пользовательские продукты не видны: только общие и свои
    stmt = select(Product).where(
        or_(Product.owner_user_id.is_(None), Product.owner_user_id == user_id)
    )
    for word in words:
        stmt = stmt.where(
            Product.name_search.like(f"%{_escape_like(word)}%", escape="\\")
        )
    stmt = stmt.order_by(
        case(
            (Product.source == "user", 0),
            (Product.code.like("off-%"), 2),
            (Product.source == "local", 1),
            else_=3,
        ),
        func.length(Product.name),
    ).limit(MAX_RESULTS * 2)
    # Один и тот же продукт может быть и в справочнике, и в кэше OFF — убираем дубли
    unique: dict[str, Product] = {}
    for product in db.scalars(stmt):
        unique.setdefault(product.name_search, product)
    return list(unique.values())[:MAX_RESULTS]


def _upsert_off_products(db: Session, parsed: list[dict]) -> list[Product]:
    """Сохраняет продукты OpenFoodFacts: новые создаёт, off-продукты обновляет."""
    unique: dict[str, dict] = {}
    for data in parsed:
        unique.setdefault(data["code"], data)
    if not unique:
        return []

    existing = {
        p.code: p
        for p in db.scalars(select(Product).where(Product.code.in_(list(unique))))
    }
    for code, data in unique.items():
        product = existing.get(code)
        if product is None:
            db.add(_new_off_product(data))
        elif product.source == "off":
            _apply_data(product, data)
            product.cached_at = utcnow()
        # source == 'local' — не трогаем

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning("Конфликт при сохранении продуктов OFF, вставка по одному")
        for code, data in unique.items():
            try:
                product = db.scalar(select(Product).where(Product.code == code))
                if product is None:
                    db.add(_new_off_product(data))
                elif product.source == "off":
                    _apply_data(product, data)
                    product.cached_at = utcnow()
                db.commit()
            except IntegrityError:
                db.rollback()
                logger.warning("Пропущен конфликтный продукт %s", code)

    return list(db.scalars(select(Product).where(Product.code.in_(list(unique)))))


def _barcode_lookup(db: Session, code: str) -> tuple[Product | None, str]:
    """Поиск по штрихкоду: (продукт или None, external_status)."""
    product = db.scalar(select(Product).where(Product.code == code))
    if product is not None:
        return _refresh_if_stale(db, product), "skipped"

    try:
        data = openfoodfacts.get_product(code)
    except ExternalServiceError as exc:
        logger.error("Ошибка OpenFoodFacts (штрихкод %s): %s", code, exc.message)
        return None, "unavailable"
    if data is None:
        return None, "ok"

    product = _new_off_product(data)
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        product = db.scalar(select(Product).where(Product.code == data["code"]))
    return product, "ok"


def get_by_barcode(db: Session, code: str) -> Product | None:
    product, _ = _barcode_lookup(db, code)
    return product


def get_by_id(db: Session, product_id: int, user_id: int | None = None) -> Product:
    product = db.get(Product, product_id)
    if product is None or (
        product.owner_user_id is not None and product.owner_user_id != user_id
    ):
        raise NotFoundError("Продукт не найден")
    return _refresh_if_stale(db, product)


def search(db: Session, q: str, user_id: int | None = None) -> SearchResult:
    """Умный поиск: локальная база, затем OpenFoodFacts (если локальных < 5)."""
    q = q.strip()

    # 1. Штрихкод
    if re.fullmatch(r"\d{8,14}", q):
        product, status = _barcode_lookup(db, q)
        return SearchResult(items=[product] if product else [], external_status=status)

    # 2-3. Локальный поиск
    q_norm = normalize_name(q)
    local = _search_local(db, q_norm.split()[:5], user_id)

    # 4-5. Хватает локальных или запрос слишком короткий
    if len(local) >= MIN_LOCAL_RESULTS or len(q_norm) < 3:
        return SearchResult(items=local, external_status="skipped")

    # 6. Кэш запросов
    cached_codes = openfoodfacts.cache_get(q_norm)
    if cached_codes is not None:
        cached = list(
            db.scalars(select(Product).where(Product.code.in_(cached_codes)))
        )
        return SearchResult(
            items=_merge(local, cached), external_status="skipped"
        )

    # 7. Запрос к OpenFoodFacts
    try:
        parsed = openfoodfacts.search_products(q)
    except ExternalServiceError as exc:
        logger.error("Ошибка OpenFoodFacts (запрос %r): %s", q, exc.message)
        return SearchResult(items=local, external_status="unavailable")

    # 8-9. Сохранение, кэш запросов, слияние
    saved = _upsert_off_products(db, parsed)
    openfoodfacts.cache_put(q_norm, [d["code"] for d in parsed])
    return SearchResult(items=_merge(local, saved), external_status="ok")


def _merge(local: list[Product], extra: list[Product]) -> list[Product]:
    """Локальные результаты, затем недостающие из OFF; local-источник — первым."""
    merged = list(local)
    seen = {p.id for p in merged}
    for product in extra:
        if product.id not in seen:
            seen.add(product.id)
            merged.append(product)
    def rank(p: Product) -> int:
        if p.source == "user":
            return 0
        if p.source == "local":
            return 2 if p.code.startswith("off-") else 1
        return 3

    merged.sort(key=rank)
    return merged[:MAX_RESULTS]


def _read_seed_file(path: Path) -> list[dict] | None:
    """Читает JSON-справочник. None — файла нет, он повреждён или пуст (использовать нельзя)."""
    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        logger.error("Файл справочника не найден: %s", path)
        return None
    except (OSError, ValueError) as exc:
        logger.error("Не удалось прочитать файл справочника %s: %s", path, exc)
        return None
    if not isinstance(data, list) or not data:
        logger.error("Файл справочника пуст или имеет неверный формат: %s", path)
        return None
    return data


def seed_local_products(db: Session) -> None:
    """Синхронизирует локальные продукты с JSON: добавляет новые, обновляет изменённые,
    удаляет исчезнувшие (по code).

    Защита от потери данных: если файл не удалось прочитать, ничего из того, что он
    описывает, не удаляется. Нет основного справочника — синхронизация пропускается целиком;
    нет выгрузки OpenFoodFacts (коды off-*) — такие продукты остаются как есть.
    """
    main_items = _read_seed_file(SEED_FILE)
    if main_items is None:
        logger.critical(
            "Основной справочник продуктов не загружен: синхронизация пропущена, "
            "продукты в базе не тронуты"
        )
        return
    off_items = _read_seed_file(SEED_OFF_FILE)
    if off_items is None:
        logger.warning(
            "Выгрузка OpenFoodFacts не загружена: продукты off-* не обновляются и не удаляются"
        )
    all_items = main_items + (off_items or [])

    existing = {
        p.code: p
        for p in db.scalars(select(Product).where(Product.source == "local"))
    }

    now: datetime = utcnow()
    added = 0
    updated = 0
    for item in all_items:
        values = {
            "name": item["name"],
            "brand": item.get("brand"),
            "name_search": normalize_name(item["name"], item.get("brand")),
            "calories": float(item["calories"]),
            "protein": float(item["protein"]),
            "fat": float(item["fat"]),
            "carbs": float(item["carbs"]),
            "image_url": item.get("image_url"),
        }
        product = existing.get(item["code"])
        if product is None:
            db.add(
                Product(
                    code=item["code"],
                    source="local",
                    cached_at=None,
                    created_at=now,
                    **values,
                )
            )
            added += 1
        elif any(getattr(product, key) != value for key, value in values.items()):
            for key, value in values.items():
                setattr(product, key, value)
            updated += 1

    # Удаляем локальные продукты, которых больше нет в загруженных файлах.
    # В дневнике остаются снимки (product_id обнуляется), свои продукты не затрагиваются.
    json_codes = {item["code"] for item in all_items}
    removed = 0
    for code, product in existing.items():
        if code in json_codes:
            continue
        if code.startswith("off-") and off_items is None:
            continue  # выгрузка OFF не загружена — её продукты не трогаем
        db.delete(product)
        removed += 1

    if added or updated or removed:
        db.commit()
        logger.info(
            "Локальные продукты: добавлено %d, обновлено %d, удалено %d",
            added,
            updated,
            removed,
        )


def create_user_product(
    db: Session,
    user_id: int,
    name: str,
    brand: str | None,
    calories: float,
    protein: float,
    fat: float,
    carbs: float,
) -> Product:
    """Создаёт личный продукт пользователя (виден только ему)."""
    count = db.scalar(
        select(func.count()).select_from(Product).where(Product.owner_user_id == user_id)
    )
    if count and count >= MAX_USER_PRODUCTS:
        raise ValidationError(
            f"Можно создать не больше {MAX_USER_PRODUCTS} своих продуктов"
        )

    product = Product(
        code=f"u-{uuid.uuid4().hex}",
        name=name,
        brand=brand,
        name_search=normalize_name(name, brand)[:512],
        calories=round(calories, 1),
        protein=round(protein, 1),
        fat=round(fat, 1),
        carbs=round(carbs, 1),
        image_url=None,
        source="user",
        owner_user_id=user_id,
        cached_at=None,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def delete_user_product(db: Session, user_id: int, product_id: int) -> None:
    """Удаляет личный продукт. Записи дневника сохраняют снимок названия и КБЖУ."""
    product = db.scalar(
        select(Product).where(
            Product.id == product_id,
            Product.owner_user_id == user_id,
            Product.source == "user",
        )
    )
    if product is None:
        raise NotFoundError("Продукт не найден")
    db.delete(product)
    db.commit()
