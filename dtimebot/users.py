from typing import Optional
from sqlalchemy import Integer, BigInteger, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import Mapped

from dtimebot.database import Base


class User(Base):
	__tablename__ = 'user'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
	created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
	deleted_at: Mapped[Optional[DateTime]] = mapped_column(DateTime)
