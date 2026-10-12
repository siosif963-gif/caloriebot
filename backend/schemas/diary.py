import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class DiaryEntryCreate(BaseModel):
    product_id: int = Field(gt=0)
    weight_g: float = Field(gt=0, le=5000)
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    entry_date: dt.date

    @field_validator("weight_g")
    @classmethod
    def _check_min_weight(cls, value: float) -> float:
        if value < 1:
            raise ValueError("вес должен быть от 1 до 5000 г")
        return value

    @field_validator("entry_date")
    @classmethod
    def _check_date_range(cls, value: dt.date) -> dt.date:
        today = dt.datetime.now(dt.timezone.utc).date()
        if value < today - dt.timedelta(days=365) or value > today + dt.timedelta(days=1):
            raise ValueError("дата должна быть не старше 365 дней и не позже завтрашней")
        return value


class DiaryEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int | None = None
    product_name: str
    product_brand: str | None = None
    meal_type: str
    weight_g: float
    calories: float
    protein: float
    fat: float
    carbs: float
    entry_date: dt.date
    created_at: dt.datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: dt.datetime) -> str:
        # В SQLite время хранится без tz, но всегда в UTC
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Macros(BaseModel):
    calories: float
    protein: float
    fat: float
    carbs: float


class DiaryDayResponse(BaseModel):
    date: dt.date
    meals: dict[str, list[DiaryEntryOut]]
    meal_totals: dict[str, Macros]
    totals: Macros
    goals: Macros
