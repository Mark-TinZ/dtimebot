from typing import Optional
from sqlalchemy import ForeignKey, Integer, DateTime, String
from sqlalchemy.orm import mapped_column, Mapped
from sqlalchemy.sql import func
from dtimebot.database import Base
from dtimebot.models.users import User
from dtimebot.models.directories import Directory
from dtimebot.models.invitations import Invitation

class Member(Base):
	__tablename__ = 'member'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	directory_id: Mapped[int] = mapped_column(ForeignKey(Directory.id))
	user_id: Mapped[int] = mapped_column(ForeignKey(User.id))
	invitation_id: Mapped[int] = mapped_column(ForeignKey(Invitation.id))
	is_active: Mapped[bool] = mapped_column(default=True)
	is_deleted: Mapped[Optional[DateTime]] = mapped_column(DateTime)
	created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

class MemberTags(Base):
	__tablename__ = 'member_tag'

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	tag: Mapped[str] = mapped_column(String(64))
	