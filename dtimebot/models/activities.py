from typing import Optional
from pydantic import BaseModel
from sqlalchemy import ForeignKey, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import mapped_column, Mapped, relationship
from dtimebot.models.users import User
from dtimebot.database import Base, JSONModel

class ActivityEmbed(BaseModel):
	location: str

class Activity(Base):
	__tablename__ = 'activity'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	owner_id: Mapped[int] = mapped_column(ForeignKey(User.id))
	title: Mapped[str] = mapped_column(String(128))
	description: Mapped[Optional[str]] = mapped_column(String(256))
	time_start: Mapped[DateTime] = mapped_column(DateTime)
	time_end: Mapped[Optional[DateTime]] = mapped_column(DateTime)
	embed: Mapped[ActivityEmbed] = mapped_column(JSONModel(ActivityEmbed))
	created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
	owner: Mapped[User] = relationship()

class ActivityTag(Base):
	__tablename__ = 'activity_tag'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	activity_id: Mapped[int]  = mapped_column(ForeignKey(Activity.id))
	tag: Mapped[str] = mapped_column(String(64))
