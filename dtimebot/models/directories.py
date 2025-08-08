from sqlalchemy import ForeignKey, Integer, String, DateTime, Boolean
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.sql import func
from dtimebot.database import Base
from dtimebot.models.users import User

class Directory(Base):
	__tablename__ = 'directory'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	owner_id: Mapped[int] = mapped_column(ForeignKey(User.id))
	name: Mapped[str] = mapped_column(String(128))
	description: Mapped[str] = mapped_column(String(256))
	is_self: Mapped[bool] = mapped_column(Boolean, default=False)
	created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
