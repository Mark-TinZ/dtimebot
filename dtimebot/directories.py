from sqlalchemy import ForeignKey, Integer, String, DateTime
from sqlalchemy.orm import mapped_column, Mapped

from dtimebot.database import Base
from dtimebot.users import User


class Directory(Base):
	__tablename__ = 'directory'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	owner_id: Mapped[int] = mapped_column(ForeignKey(User.id))
	name: Mapped[str] = mapped_column(String(128))
	description: Mapped[str] = mapped_column(String(256))
	cteated_at: Mapped[DateTime] = mapped_column(DateTime)

