import datetime as dt

from pydantic import BaseModel

from schemas.diary import Macros


class StatsDay(BaseModel):
    date: dt.date
    calories: float
    protein: float
    fat: float
    carbs: float


class StatsResponse(BaseModel):
    start_date: dt.date
    end_date: dt.date
    days: list[StatsDay]
    averages: Macros
    days_logged: int
    goal_calories: int
