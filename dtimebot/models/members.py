from typing import Optional
from sqlalchemy import ForeignKey, Integer, DateTime, String, Boolean
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy.sql import func
from dtimebot.database import Base
from dtimebot.models.users import User
from dtimebot.models.directories import Directory
from dtimebot.models.invitations import Invitation

class Member(Base):
    __tablename__ = 'member'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    directory_id: Mapped[int] = mapped_column(ForeignKey(Directory.id), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), nullable=False)
    invitation_id: Mapped[Optional[int]] = mapped_column(ForeignKey(Invitation.id), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[Optional[DateTime]] = mapped_column(DateTime)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())

class MemberTag(Base):
    __tablename__ = 'member_tag'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(ForeignKey(Member.id), nullable=False)
    tag: Mapped[str] = mapped_column(String(64), nullable=False)