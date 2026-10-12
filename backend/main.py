"""Точка входа FastAPI: CORS, роутеры, обработчики ошибок, инициализация БД."""
import logging
from contextlib import asynccontextmanager
from http import HTTPStatus
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.engine import make_url
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from database import init_db
from routers import diary, products, stats, users
from services.errors import (
    AuthError,
    ExternalServiceError,
    NotFoundError,
    ValidationError,
)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("caloriebot")


def _ensure_db_dir() -> None:
    """Создаёт папку для файла SQLite, если её нет."""
    url = make_url(settings.DATABASE_URL)
    if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.BOT_TOKEN and not settings.DEV_MODE:
        logger.critical(
            "BOT_TOKEN не задан и DEV_MODE выключен: запуск невозможен. "
            "Укажите BOT_TOKEN в переменных окружения."
        )
        raise RuntimeError("BOT_TOKEN не задан")
    if settings.DEV_MODE:
        logger.warning("ВНИМАНИЕ: включён DEV_MODE — авторизация через initData отключена")
    _ensure_db_dir()
    init_db()
    logger.info("CalorieBot запущен")
    yield


app = FastAPI(title="CalorieBot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins_list,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,
)


def _error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


@app.exception_handler(NotFoundError)
def handle_not_found(request: Request, exc: NotFoundError) -> JSONResponse:
    return _error(404, exc.message or "Не найдено")


@app.exception_handler(ValidationError)
def handle_validation(request: Request, exc: ValidationError) -> JSONResponse:
    return _error(422, exc.message or "Некорректные данные")


@app.exception_handler(ExternalServiceError)
def handle_external(request: Request, exc: ExternalServiceError) -> JSONResponse:
    return _error(503, exc.message or "Внешний сервис временно недоступен")


@app.exception_handler(AuthError)
def handle_auth(request: Request, exc: AuthError) -> JSONResponse:
    return _error(401, "Откройте приложение через Telegram")


@app.exception_handler(RequestValidationError)
def handle_request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    if errors:
        first = errors[0]
        field = ".".join(
            str(p) for p in first.get("loc", ()) if p not in ("body", "query", "path")
        )
        reason = str(first.get("msg", "неверное значение"))
        reason = reason.removeprefix("Value error, ")
        return _error(422, f"Некорректные данные: {field or 'запрос'} — {reason}")
    return _error(422, "Некорректные данные")


@app.exception_handler(StarletteHTTPException)
def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail if isinstance(exc.detail, str) else "Ошибка запроса"
    if exc.status_code == 404 and detail == HTTPStatus.NOT_FOUND.phrase:
        detail = "Не найдено"
    elif exc.status_code == 405 and detail == HTTPStatus.METHOD_NOT_ALLOWED.phrase:
        detail = "Метод не поддерживается"
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(Exception)
def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Необработанное исключение: %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return _error(500, "Внутренняя ошибка сервера")


app.include_router(users.router)
app.include_router(products.router)
app.include_router(diary.router)
app.include_router(stats.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
