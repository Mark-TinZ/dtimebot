from typing import Optional
from sqlalchemy import ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import mapped_column, Mapped

from dtimebot.database import Base
from dtimebot.users import User


class Invitation(Base):
	__tablename__ = 'invitation'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	owner_id: Mapped[int] = mapped_column(ForeignKey(User.id))
	filter: Mapped[Optional[str]] = mapped_column(String(128))
	valid_until: Mapped[Optional[DateTime]] = mapped_column(DateTime)
	max_uses: Mapped[Optional[int]] = mapped_column(Integer)
	used_count: Mapped[int] = mapped_column(Integer)
	code: Mapped[str] = mapped_column(String(64))
	create_at: Mapped[DateTime] = mapped_column(DateTime)
