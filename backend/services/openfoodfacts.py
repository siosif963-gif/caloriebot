"""HTTP-клиент OpenFoodFacts: поиск, получение по штрихкоду, парсинг, кэш и лимит запросов."""
import logging
import math
import threading
import time
from collections import deque

import httpx

from config import settings
from services.errors import ExternalServiceError

logger = logging.getLogger(__name__)

FIELDS = "code,product_name,product_name_ru,brands,nutriments,image_front_small_url"
CACHE_TTL_SECONDS = 10 * 60
CACHE_MAX_ENTRIES = 500
RATE_WINDOW_SECONDS = 60

# Кэш поисковых запросов: нормализованный запрос -> (время, список кодов продуктов)
_query_cache: dict[str, tuple[float, list[str]]] = {}
_cache_lock = threading.Lock()

# Временные метки поисковых вызовов для ограничителя частоты
_search_calls: deque[float] = deque()
_rate_lock = threading.Lock()


def cache_get(query_norm: str) -> list[str] | None:
    """Возвращает коды из кэша запросов, если запись моложе 10 минут."""
    with _cache_lock:
        entry = _query_cache.get(query_norm)
        if entry is None:
            return None
        saved_at, codes = entry
        if time.time() - saved_at > CACHE_TTL_SECONDS:
            del _query_cache[query_norm]
            return None
        return list(codes)


def cache_put(query_norm: str, codes: list[str]) -> None:
    """Кладёт результат в кэш; при переполнении удаляет самую старую запись."""
    with _cache_lock:
        _query_cache.pop(query_norm, None)
        while len(_query_cache) >= CACHE_MAX_ENTRIES:
            oldest_key = next(iter(_query_cache))
            del _query_cache[oldest_key]
        _query_cache[query_norm] = (time.time(), list(codes))


def _acquire_search_slot() -> None:
    """Ограничитель частоты: не больше N поисковых запросов за 60 секунд."""
    now = time.time()
    with _rate_lock:
        while _search_calls and now - _search_calls[0] > RATE_WINDOW_SECONDS:
            _search_calls.popleft()
        if len(_search_calls) >= settings.OFF_SEARCH_MAX_PER_MINUTE:
            raise ExternalServiceError("Превышен лимит запросов к OpenFoodFacts")
        _search_calls.append(now)


def _headers() -> dict[str, str]:
    return {"User-Agent": f"CalorieBot/1.0 ({settings.OFF_CONTACT_EMAIL})"}


def _get_json(url: str, params: dict[str, str | int]) -> dict:
    """GET-запрос к OpenFoodFacts. Любая ошибка -> ExternalServiceError."""
    try:
        with httpx.Client(
            timeout=httpx.Timeout(8.0, connect=3.0), headers=_headers()
        ) as client:
            response = client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise ExternalServiceError(f"OpenFoodFacts недоступен: {exc!r}") from exc

    if response.status_code != 200:
        raise ExternalServiceError(
            f"OpenFoodFacts вернул код {response.status_code}"
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise ExternalServiceError("OpenFoodFacts вернул невалидный JSON") from exc
    if not isinstance(data, dict):
        raise ExternalServiceError("OpenFoodFacts вернул неожиданный формат ответа")
    return data


def _to_float(value: object) -> float | None:
    """Безопасное приведение к float: строки, None и мусор не роняют код."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def parse_product(raw: dict) -> dict | None:
    """Превращает сырой продукт OpenFoodFacts в словарь для БД или None (пропустить)."""
    if not isinstance(raw, dict):
        return None

    code = raw.get("code")
    if isinstance(code, int):
        code = str(code)
    if not isinstance(code, str) or not code.strip() or len(code.strip()) > 64:
        return None
    code = code.strip()

    name = ""
    for key in ("product_name_ru", "product_name"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            name = value.strip()
            break
    if not name:
        return None
    name = name[:255]

    brand: str | None = None
    brands = raw.get("brands")
    if isinstance(brands, str):
        first = brands.split(",")[0].strip()
        brand = first[:255] or None

    nutriments = raw.get("nutriments")
    if not isinstance(nutriments, dict):
        return None

    calories = _to_float(nutriments.get("energy-kcal_100g"))
    if calories is None:
        kj = _to_float(nutriments.get("energy-kj_100g"))
        if kj is not None:
            calories = kj / 4.184
    if calories is None:
        energy = _to_float(nutriments.get("energy_100g"))  # это кДж
        if energy is not None:
            calories = energy / 4.184
    if calories is None:
        return None

    protein = _to_float(nutriments.get("proteins_100g")) or 0.0
    fat = _to_float(nutriments.get("fat_100g")) or 0.0
    carbs = _to_float(nutriments.get("carbohydrates_100g")) or 0.0

    if not 0 <= calories <= 900:
        return None
    if not all(0 <= v <= 100 for v in (protein, fat, carbs)):
        return None

    image_url = raw.get("image_front_small_url")
    if not isinstance(image_url, str) or not image_url.startswith("https://"):
        image_url = None
    elif len(image_url) > 512:
        image_url = None

    return {
        "code": code,
        "name": name,
        "brand": brand,
        "calories": round(calories, 1),
        "protein": round(protein, 1),
        "fat": round(fat, 1),
        "carbs": round(carbs, 1),
        "image_url": image_url,
    }


def search_products(query: str) -> list[dict]:
    """Поиск по названию. Возвращает уже распарсенные продукты (parse_product)."""
    _acquire_search_slot()
    data = _get_json(
        f"{settings.OFF_BASE_URL}/cgi/search.pl",
        {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": 20,
            "fields": FIELDS,
        },
    )
    products = data.get("products")
    if not isinstance(products, list):
        raise ExternalServiceError("В ответе OpenFoodFacts нет списка products")

    result: list[dict] = []
    for raw in products:
        parsed = parse_product(raw)
        if parsed is not None:
            result.append(parsed)
    return result


def get_product(code: str) -> dict | None:
    """Продукт по штрихкоду. None — продукта нет в OpenFoodFacts (не ошибка)."""
    data = _get_json(
        f"{settings.OFF_BASE_URL}/api/v2/product/{code}.json", {"fields": FIELDS}
    )
    if data.get("status") != 1:
        return None
    raw = data.get("product")
    if not isinstance(raw, dict):
        return None
    if not raw.get("code"):
        raw = {**raw, "code": code}
    return parse_product(raw)
