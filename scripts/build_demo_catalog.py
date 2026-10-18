"""Собирает frontend/data/products.json для демо-режима из данных бэкенда.

Формат файла: {"v": 1, "items": [[code, name, brand, kcal, protein, fat, carbs, image_url], ...]}
(компактные массивы вместо объектов, чтобы уложиться в бюджет по размеру).

Запуск из корня репозитория:  python3 scripts/build_demo_catalog.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUDGET_BYTES = 300 * 1024

curated = json.loads((ROOT / "backend/data/russian_products.json").read_text(encoding="utf-8"))
off_dump = json.loads((ROOT / "backend/data/off_ru_products.json").read_text(encoding="utf-8"))

# Приоритет: справочник и меню сетей, затем магазины, затем выгрузка OpenFoodFacts (сначала с фото)
groups = [
    [p for p in curated if not p["code"].startswith("st-")],
    [p for p in curated if p["code"].startswith("st-")],
    [p for p in off_dump if p.get("image_url")],
    [p for p in off_dump if not p.get("image_url")],
]


def row(p: dict) -> list:
    cells = [p["code"], p["name"], p.get("brand"), p["calories"], p["protein"], p["fat"], p["carbs"]]
    if p.get("image_url"):
        cells.append(p["image_url"])
    return cells


def dump(items: list[list]) -> str:
    return json.dumps({"v": 1, "items": items}, ensure_ascii=False, separators=(",", ":"))


items: list[list] = []
seen: set[tuple[str, str]] = set()
for group in groups:
    for p in group:
        key = (p["name"].lower(), (p.get("brand") or "").lower())
        if key in seen:
            continue
        candidate = row(p)
        if len(dump(items + [candidate]).encode("utf-8")) > BUDGET_BYTES:
            continue
        seen.add(key)
        items.append(candidate)

out = ROOT / "frontend/data/products.json"
out.write_text(dump(items), encoding="utf-8")
print(f"{len(items)} продуктов, {out.stat().st_size / 1024:.0f} КБ -> {out.relative_to(ROOT)}")
