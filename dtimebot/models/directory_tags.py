from sqlalchemy import ForeignKey, Integer, String	
from sqlalchemy.orm import mapped_column, Mapped

from dtimebot.database import Base
from dtimebot.models.directories import Directory


class DirectoryTag(Base):
	__tablename__ = 'directory_tag'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	directory_id: Mapped[int]  = mapped_column(ForeignKey(Directory.id))
	tag: Mapped[str] = mapped_column(String(64))
