import datetime as dt

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from routers.deps import get_current_user
from schemas.diary import DiaryDayResponse, DiaryEntryCreate, DiaryEntryOut
from services import diary_service

router = APIRouter(prefix="/api/diary", tags=["diary"])


@router.post("/add", response_model=DiaryEntryOut, status_code=201)
def add_entry(
    payload: DiaryEntryCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiaryEntryOut:
    entry = diary_service.add_entry(
        db,
        user,
        product_id=payload.product_id,
        weight_g=payload.weight_g,
        meal_type=payload.meal_type,
        entry_date=payload.entry_date,
    )
    return DiaryEntryOut.model_validate(entry)


@router.get("/day", response_model=DiaryDayResponse)
def get_day(
    date: dt.date = Query(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DiaryDayResponse:
    return DiaryDayResponse.model_validate(diary_service.get_day(db, user, date))


@router.delete("/{entry_id}", status_code=204)
def delete_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    diary_service.delete_entry(db, user, entry_id)
    return Response(status_code=204)
