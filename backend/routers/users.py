from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from routers.deps import get_current_user
from schemas.user import UserOut, UserSettingsUpdate
from services import user_service

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/settings", response_model=UserOut)
def get_settings(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.put("/settings", response_model=UserOut)
def put_settings(
    payload: UserSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    updated = user_service.update_settings(db, user, payload.model_dump())
    return UserOut.model_validate(updated)
