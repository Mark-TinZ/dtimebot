# dtimebot/services/directory_service.py
"""
Сервис для работы с директориями.
"""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from dtimebot.database import LocalSession
from dtimebot.models.directories import Directory
from dtimebot.models.users import User
from dtimebot.logs import main_logger

logger = main_logger.getChild('directory_service')

async def create_directory(owner_telegram_id: int, name: str, description: str = "") -> Optional[Directory]:
	"""
	Создает новую директорию для пользователя.\n
	:param owner_telegram_id: Telegram ID владельца.
	:param name: Название директории.
	:param description: Описание директории.
	:return: Объект Directory или None в случае ошибки.
	"""
	try:
		async with LocalSession() as session:
			# Найти пользователя по telegram_id
			stmt = select(User).where(User.telegram_id == owner_telegram_id)
			result = await session.execute(stmt)
			user = result.scalar_one_or_none()

			if not user:
				logger.warning(f"A user with telegram_id={owner_telegram_id} was not found.")
				return None

			# Создать директорию
			new_directory = Directory(
				owner_id=user.id,
				name=name,
				description=description
			)
			session.add(new_directory)
			await session.commit()
			await session.refresh(new_directory)
			logger.info(f"Directory '{name}' (ID: {new_directory.id}) has been created for user {owner_telegram_id}.")
			return new_directory

	except SQLAlchemyError as e:
		logger.error(f"SQLAlchemy error occurred while creating directory for {owner_telegram_id}: {e}", exc_info=True)
		return None
	except Exception as e:
		logger.error(f"An unexpected error occurred while creating directory for {owner_telegram_id}: {e}", exc_info=True)
		return None

async def get_user_directories(owner_telegram_id: int) -> List[Directory]:
	"""
	Получает список директорий пользователя.\n
	:param owner_telegram_id: Telegram ID владельца.
	:return: Список объектов Directory.
	"""
	try:
		async with LocalSession() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				logger.warning(f"A user with telegram_id={owner_telegram_id} was not found.")
				return []

			# Найти его директории
			stmt_dirs = select(Directory).where(Directory.owner_id == user.id)
			result_dirs = await session.execute(stmt_dirs)
			directories = list(result_dirs.scalars().all())
			logger.info(f"Found {len(directories)} directories for user {owner_telegram_id}.")
			return directories

	except SQLAlchemyError as e:
		logger.error(f"SQLAlchemy error occurred while retrieving directories for {owner_telegram_id}: {e}", exc_info=True)
		return []
	except Exception as e:
		logger.error(f"An unexpected error occurred while retrieving directories for {owner_telegram_id}: {e}", exc_info=True)
		return []

async def delete_directory(owner_telegram_id: int, directory_id: int) -> bool:
	"""
	Удаляет директорию пользователя по ID.\n
	:param owner_telegram_id: Telegram ID владельца.
	:param directory_id: ID директории.
	:return: True, если успешно удалено, иначе False.
	"""
	try:
		async with LocalSession() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				logger.warning(f"A user with telegram_id={owner_telegram_id} was not found.")
				return False

			# Найти директорию, принадлежащую этому пользователю
			stmt_dir = select(Directory).where(Directory.id == directory_id, Directory.owner_id == user.id)
			result_dir = await session.execute(stmt_dir)
			directory = result_dir.scalar_one_or_none()

			if not directory:
				logger.warning(f"Directory with ID={directory_id} not found or does not belong to user {owner_telegram_id}.")
				return False

			# Удалить директорию
			await session.delete(directory)
			await session.commit()
			logger.info(f"Directory '{directory.name}' (ID: {directory_id}) has been deleted by user {owner_telegram_id}.")
			return True

	except SQLAlchemyError as e:
		logger.error(f"SQLAlchemy error occurred while deleting directory {directory_id} for {owner_telegram_id}: {e}", exc_info=True)
		return False
	except Exception as e:
		logger.error(f"An unexpected error occurred while deleting directory {directory_id} for {owner_telegram_id}: {e}", exc_info=True)
		return False
