from typing import Optional
from sqlalchemy import ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import mapped_column, Mapped

from dtimebot.database import Base
from dtimebot.users import User


class Member(Base):
	__tablename__ = 'member'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)