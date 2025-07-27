from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import mapped_column, Mapped

from dtimebot.database import Base
from dtimebot.directories import Directory


class Access_rule(Base):
	__tablename__ = 'access_rule'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	directory_id: Mapped[int]  = mapped_column(ForeignKey(Directory.id))