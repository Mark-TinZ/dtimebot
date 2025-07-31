from sqlalchemy import ForeignKey, Integer, String	
from sqlalchemy.orm import mapped_column, Mapped

from dtimebot.database import Base
from dtimebot.models.directories import Directory


class AccessRule(Base):
	__tablename__ = 'access_rule'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	directory_id: Mapped[int]  = mapped_column(ForeignKey(Directory.id))

class AccessRulePermission(Base):
	__tablename__ = 'access_rule_permission'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	rure_id: Mapped[int]  = mapped_column(ForeignKey(AccessRule.id))
	prermission: Mapped[str] = mapped_column(String(64))

class AccessRuleFilter(Base):
	__tablename__ = 'access_rule_filter'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	rure_id: Mapped[int]  = mapped_column(ForeignKey(AccessRule.id))
	filter_type: Mapped[str] = mapped_column(String(16)) # object / subject
	tag: Mapped[str] = mapped_column(String(64))

