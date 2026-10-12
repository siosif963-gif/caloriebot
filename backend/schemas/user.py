from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    telegram_id: int
    first_name: str
    username: str | None = None
    daily_calories: int
    daily_protein: int
    daily_fat: int
    daily_carbs: int


class UserSettingsUpdate(BaseModel):
    daily_calories: int = Field(ge=800, le=10000)
    daily_protein: int = Field(ge=0, le=500)
    daily_fat: int = Field(ge=0, le=500)
    daily_carbs: int = Field(ge=0, le=1000)
