# CalorieBot — Telegram Mini App

[![Tests](https://github.com/siosif963-gif/caloriebot/actions/workflows/tests.yml/badge.svg)](https://github.com/siosif963-gif/caloriebot/actions/workflows/tests.yml)

- **Бот в Telegram:** [@easyeatcounter_bot](https://t.me/easyeatcounter_bot) (кнопка меню открывает мини-апп).
- **Демо в браузере, без Telegram:** https://siosif963-gif.github.io/caloriebot/ (данные хранятся только у вас в браузере, подробности в разделе «Демо-режим»).

## О проекте

CalorieBot — Telegram Mini App для ежедневного дневника питания. Пользователь находит продукт (по названию или штрихкоду), вводит вес порции и приём пищи, а приложение считает калории и БЖУ и показывает прогресс к дневной норме. Поиск комбинированный: сначала локальная база российских продуктов, затем OpenFoodFacts с сохранением найденного в локальную БД.

Приложением пользуется небольшая группа реальных пользователей.

**Для кого подходит.** Такой мини-апп подходит для фитнес-клубов, нутрициологов и онлайн-марафонов питания: клиенты ведут дневник прямо в Telegram, без установки отдельного приложения и регистрации.

**Стек:** FastAPI + SQLAlchemy 2.0 + SQLite (бэкенд), Vanilla JS + Chart.js (фронтенд на GitHub Pages), pytest, GitHub Actions, Docker.

## Скриншоты

![Все экраны CalorieBot](screenshots/00-overview.jpg)

| Дневник | Поиск | Порция |
|:---:|:---:|:---:|
| <img src="screenshots/01-diary.jpg" width="240"> | <img src="screenshots/02-search.jpg" width="240"> | <img src="screenshots/03-add-portion.jpg" width="240"> |

| Статистика | Свой продукт | Настройки |
|:---:|:---:|:---:|
| <img src="screenshots/04-stats.jpg" width="240"> | <img src="screenshots/05-create-product.jpg" width="240"> | <img src="screenshots/06-settings.jpg" width="240"> |

## Возможности

- Дневник питания по приёмам пищи: калории и БЖУ с прогрессом к дневной норме.
- Умный поиск по названию и штрихкоду: локальная база (сети общепита, магазины, базовые продукты) и OpenFoodFacts.
- Свои продукты: создание, видны только автору; проверка БЖУ на 100 г.
- Статистика за неделю и месяц с графиком и средними значениями.
- Авторизация через подпись Telegram `initData`, тема Telegram (светлая и тёмная).
- Демо-режим: приложение работает в обычном браузере без сервера.

## Демо-режим

Если открыть приложение **не из Telegram**, оно запускается в демо-режиме: сервер не нужен, все данные остаются в вашем браузере.

- Продукты берутся из встроенной базы (`frontend/data/products.json`, около 1800 позиций), поиск по названию и штрихкоду работает без сети.
- Дневник, свои продукты и нормы хранятся в `localStorage`. Если хранилище недоступно, данные живут в памяти страницы.
- При первом открытии дневник заполнен примерами за последние 7 дней, чтобы статистика не была пустой.
- Сверху показана плашка «Демо-режим» с кнопкой «Сбросить демо».
- Включить явно: добавьте `?demo=1` к адресу, например `https://siosif963-gif.github.io/caloriebot/?demo=1`.
- **Внутри Telegram демо никогда не включается**, даже с `?demo=1`: там всегда настоящий бэкенд.
- Для разработки с локальным бэкендом: откройте страницу с `?demo=0` (демо выключено, запросы идут на `API_BASE_URL`).

Реализация: `frontend/api-demo.js` повторяет интерфейс `frontend/api.js` (те же функции и форматы ответов), а `api.js` выбирает нужную реализацию. Каталог пересобирается скриптом `scripts/build_demo_catalog.py`.

## Запуск через Docker

Нужен только Docker. Из корня репозитория:

```bash
cp .env.example .env        # задайте BOT_TOKEN (или DEV_MODE=true для проверки без Telegram)
docker compose up --build
```

Бэкенд откроется на http://localhost:8000 (`/api/health`, `/docs`). База SQLite лежит в томе `caloriebot-data` и переживает перезапуск и пересоздание контейнера. Остановка: `docker compose down` (данные остаются), `docker compose down -v` (вместе с данными).

Контейнер работает не от root. Dockerfile лежит в `backend/docker/Dockerfile`, а не в корне `backend/`, чтобы Railway не подхватил его вместо своей сборки.

## Локальный запуск без Docker

Бэкенд:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # DEV_MODE=true и FRONTEND_ORIGINS=http://localhost:5500
uvicorn main:app --reload
```

Проверка: http://localhost:8000/api/health и http://localhost:8000/docs.

Фронтенд (из папки `frontend`):

```bash
python -m http.server 5500
```

Откройте http://localhost:5500: вне Telegram это демо-режим, сервер не нужен. Чтобы работать с локальным бэкендом, временно поставьте в `frontend/api.js` `API_BASE_URL = 'http://localhost:8000'` и откройте http://localhost:5500/?demo=0 (бэкенд должен быть запущен с `DEV_MODE=true`).

## Тесты

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

Тесты используют отдельную временную SQLite на каждый тест и не обращаются к сети (OpenFoodFacts подменён). На каждый push и pull request они запускаются в GitHub Actions.

## Создание бота

В @BotFather: `/newbot`, сохраните токен. Затем `/mybots` → ваш бот → Bot Settings → Menu Button → укажите URL фронтенда на GitHub Pages.

## Деплой

**Бэкенд (Railway).** New Project → Deploy from GitHub repo → Root Directory `backend` → Volume на `/data` → переменные из `backend/.env.example` (`DATABASE_URL=sqlite:////data/database.db`, `DEV_MODE=false`, `BOT_TOKEN`, `FRONTEND_ORIGINS`) → Start Command `uvicorn main:app --host 0.0.0.0 --port $PORT` → Generate Domain.

**Бэкенд (Render).** Web Service с Root Directory `backend` и той же командой запуска. Для сохранности данных нужен Persistent Disk на `/data` (платный тариф): без диска база стирается при каждом деплое, а бесплатный сервис засыпает.

**Фронтенд (GitHub Pages).** Впишите домен бэкенда в `API_BASE_URL` (`frontend/api.js`), включите Settings → Pages → Source: GitHub Actions и сделайте push в `main`. Адрес вида `https://username.github.io/caloriebot/` укажите в Menu Button бота, а origin `https://username.github.io` добавьте в `FRONTEND_ORIGINS` бэкенда.

## Частые проблемы

- **Ошибка CORS** — проверьте `FRONTEND_ORIGINS` (только origin, без пути).
- **401** — приложение открыто не через Telegram или неверный `BOT_TOKEN`.
- **Пропали данные** — не подключён Volume / Disk.

## Данные и лицензии

Код распространяется по лицензии MIT (см. [LICENSE](LICENSE)).

Часть данных о продуктах получена из [Open Food Facts](https://world.openfoodfacts.org) (лицензия ODbL, © участники Open Food Facts). Меню сетей общепита и магазинов собрано из открытых таблиц пищевой ценности; значения справочные и могут отличаться от данных на упаковке.
