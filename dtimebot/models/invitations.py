from typing import Optional
from sqlalchemy import ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.sql import func
from dtimebot.database import Base
from dtimebot.models.users import User

class Invitation(Base):
	__tablename__ = 'invitation'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	owner_id: Mapped[int] = mapped_column(ForeignKey(User.id))
	filter: Mapped[Optional[str]] = mapped_column(String(128))
	valid_until: Mapped[Optional[DateTime]] = mapped_column(DateTime)
	max_uses: Mapped[Optional[int]] = mapped_column(Integer)
	used_count: Mapped[int] = mapped_column(Integer, default=0)
	code: Mapped[str] = mapped_column(String(64))
	created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
