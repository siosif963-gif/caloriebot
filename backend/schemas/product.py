from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    brand: str | None = None
    calories: float
    protein: float
    fat: float
    carbs: float
    image_url: str | None = None
    source: str


class ProductSearchResponse(BaseModel):
    items: list[ProductOut]
    external_status: Literal["ok", "skipped", "unavailable"]


class ProductCreate(BaseModel):
    """Свой продукт пользователя. Все значения КБЖУ — на 100 г."""

    name: str = Field(min_length=2, max_length=100)
    brand: str | None = Field(default=None, max_length=100)
    calories: float = Field(ge=0, le=900)
    protein: float = Field(ge=0, le=100)
    fat: float = Field(ge=0, le=100)
    carbs: float = Field(ge=0, le=100)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("название должно содержать минимум 2 символа")
        return value

    @field_validator("brand")
    @classmethod
    def _strip_brand(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = " ".join(value.split())
        return value or None
