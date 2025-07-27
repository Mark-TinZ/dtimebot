from typing import Optional
from pydantic import BaseModel
from sqlalchemy import Column, ForeignKey, Integer, BigInteger, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import mapped_column, Mapped, relationship

from dtimebot.users import User
from dtimebot.database import Base


class ActivityEmbed(BaseModel):
	pass

class Activity(Base):
	__tablename__ = 'activity'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	owner_id: Mapped[int] = mapped_column(ForeignKey(User.id))
	title: Mapped[str] = mapped_column(String(128))
	description: Mapped[Optional[str]] = mapped_column(String(258))
	time_start: Mapped[DateTime] = mapped_column(DateTime)
	time_end: Mapped[Optional[DateTime]] = mapped_column(DateTime)
	embed: Mapped[Optional[str]] = mapped_column(String(256))
	create_at: Mapped[DateTime] = mapped_column(DateTime)

	owner: Mapped[User] = relationship()
