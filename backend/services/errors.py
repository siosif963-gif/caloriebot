"""Исключения сервисного слоя. Роутеры/main.py превращают их в HTTP-ответы."""


class ServiceError(Exception):
    """Базовое исключение сервисов; message — текст для пользователя."""

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(ServiceError):
    """Объект не найден (404)."""


class ValidationError(ServiceError):
    """Ошибка бизнес-валидации входных данных (422)."""


class ExternalServiceError(ServiceError):
    """Внешний сервис (OpenFoodFacts) недоступен или ответил ошибкой (503)."""


class AuthError(ServiceError):
    """Неверный или просроченный initData (401)."""
