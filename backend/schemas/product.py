from typing import Literal

from pydantic import BaseModel, ConfigDict


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
