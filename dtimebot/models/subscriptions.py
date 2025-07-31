from sqlalchemy import ForeignKey, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import mapped_column, Mapped
from dtimebot.database import Base
from dtimebot.models.users import User
from dtimebot.models.directories import Directory


class Subscription(Base):
	__tablename__ = 'subscription'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	directory_id: Mapped[int] = mapped_column(ForeignKey(Directory.id))
	owner_id: Mapped[int] = mapped_column(ForeignKey(User.id))
	type: Mapped[str] = mapped_column(String(64))
	entry: Mapped[int] = mapped_column(Integer)
	is_active: Mapped[bool] = mapped_column(Boolean)
	created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
