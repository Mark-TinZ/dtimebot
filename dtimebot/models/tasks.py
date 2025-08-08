from typing import Optional
from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import mapped_column, Mapped, relationship
from dtimebot.database import Base, JSONModel
from dtimebot.models.activities import ActivityEmbed
from dtimebot.models.users import User
from dtimebot.models.directories import Directory


class Task(Base):
	__tablename__ = 'task'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	owner_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
	directory_id: Mapped[Optional[int]] = mapped_column(ForeignKey(Directory.id), nullable=True)
	title: Mapped[str] = mapped_column(String(128), nullable=False)
	description: Mapped[Optional[str]] = mapped_column(String(256))
	time_start: Mapped[Optional[DateTime]] = mapped_column(DateTime)
	time_end: Mapped[Optional[DateTime]] = mapped_column(DateTime)
	embed: Mapped[Optional[ActivityEmbed]] = mapped_column(JSONModel(ActivityEmbed), nullable=True)
	created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

	owner: Mapped[User] = relationship()
	directory: Mapped[Optional[Directory]] = relationship()

class TaskTag(Base):
	__tablename__ = 'task_tag'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	task_id: Mapped[int] = mapped_column(ForeignKey(Task.id), nullable=False)
	tag: Mapped[str] = mapped_column(String(64), nullable=False)