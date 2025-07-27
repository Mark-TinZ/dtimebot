from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import mapped_column, Mapped

from dtimebot.database import Base
from dtimebot.activities import Activity


class Activity_tag(Base):
	__tablename__ = 'activity_tag'

	activity_id: Mapped[int]  = mapped_column(ForeignKey(Activity.id))
	tag: Mapped[str] = mapped_column(String(64))