import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from routers.deps import get_current_user
from schemas.stats import StatsResponse
from services import stats_service

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
def get_stats(
    start_date: dt.date = Query(...),
    end_date: dt.date = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StatsResponse:
    return StatsResponse.model_validate(
        stats_service.get_stats(db, user, start_date, end_date)
    )
