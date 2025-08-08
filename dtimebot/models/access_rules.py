from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import mapped_column, Mapped, relationship

from dtimebot.database import Base
from dtimebot.models.directories import Directory


class AccessRule(Base):
    __tablename__ = 'access_rule'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    directory_id: Mapped[int] = mapped_column(ForeignKey(Directory.id), nullable=False)

class AccessRulePermission(Base):
    __tablename__ = 'access_rule_permission'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey(AccessRule.id), nullable=False)
    permission: Mapped[str] = mapped_column(String(64), nullable=False)

class AccessRuleFilter(Base):
    __tablename__ = 'access_rule_filter'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey(AccessRule.id), nullable=False)
    filter_type: Mapped[str] = mapped_column(String(16)) # object / subject
    tag: Mapped[str] = mapped_column(String(64))
