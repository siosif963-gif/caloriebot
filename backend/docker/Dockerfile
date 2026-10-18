# Образ бэкенда CalorieBot для локального запуска (docker compose).
# Лежит в docker/, а не в корне backend/, чтобы Railway не подхватил его вместо
# текущей сборки: деплой на Railway остаётся как был.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Запуск не от root
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app . .

# База хранится в томе /data (владелец — app, чтобы новый volume получил нужные права)
RUN mkdir -p /data && chown app:app /data
ENV DATABASE_URL=sqlite:////data/database.db \
    PORT=8000
VOLUME ["/data"]

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8000'), timeout=4)"]

# sh -c нужен для подстановки ${PORT}; exec отдаёт процесс uvicorn сигналам Docker
# hadolint ignore=DL3025
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
