from sqlalchemy import Column, Integer, BigInteger, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Task(Base):
	__tablename__ = 'users'

	id = Column(Integer, primary_key=True, autoincrement=True)
	username = Column(String(50), nullable=False, unique=True)
	full_name = Column(String(100), nullable=True)
	telegram_id = Column(BigInteger, nullable=False, unique=True)
	created_at = Column(DateTime, server_default=func.now())
