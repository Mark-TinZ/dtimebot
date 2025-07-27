from sqlalchemy import ForeignKey, String	
from sqlalchemy.orm import mapped_column, Mapped

from dtimebot.database import Base
from dtimebot.directories import Directory


class Directory_tag(Base):
	__tablename__ = 'directory_tag'

	directory_id: Mapped[int]  = mapped_column(ForeignKey(Directory.id))
	tag: Mapped[str] = mapped_column(String(64))