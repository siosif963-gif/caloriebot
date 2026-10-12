from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base, utcnow

if TYPE_CHECKING:
    from models.diary_entry import DiaryEntry


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    first_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    daily_calories: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    daily_protein: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    daily_fat: Mapped[int] = mapped_column(Integer, nullable=False, default=67)
    daily_carbs: Mapped[int] = mapped_column(Integer, nullable=False, default=250)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )

    entries: Mapped[list["DiaryEntry"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
