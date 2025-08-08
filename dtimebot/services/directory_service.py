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
from dtimebot.models.directory_tags import DirectoryTag # Добавим импорт

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


async def add_tag_to_directory(owner_telegram_id: int, directory_id: int, tag: str) -> bool:
	"""
	Добавляет тег к директории.
	:param owner_telegram_id: Telegram ID владельца директории.
	:param directory_id: ID директории.
	:param tag: Тег для добавления.
	:return: True, если успешно, иначе False.
	"""
	try:
		async with LocalSession() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				logger.warning(f"Пользователь с telegram_id={owner_telegram_id} не найден.")
				return False

			# Найти директорию, принадлежащую этому пользователю
			stmt_dir = select(Directory).where(Directory.id == directory_id, Directory.owner_id == user.id)
			result_dir = await session.execute(stmt_dir)
			directory = result_dir.scalar_one_or_none()

			if not directory:
				logger.warning(f"Директория с ID={directory_id} не найдена или не принадлежит пользователю {owner_telegram_id}.")
				return False

			# Проверить, существует ли уже такой тег
			stmt_tag_check = select(DirectoryTag).where(
				DirectoryTag.directory_id == directory_id,
				DirectoryTag.tag == tag
			)
			result_tag_check = await session.execute(stmt_tag_check)
			existing_tag = result_tag_check.scalar_one_or_none()

			if existing_tag:
				logger.info(f"Тег '{tag}' уже существует для директории {directory_id}.")
				return True # Считаем, что операция успешна, если тег уже есть

			# Добавить тег
			new_tag = DirectoryTag(directory_id=directory_id, tag=tag)
			session.add(new_tag)
			await session.commit()
			logger.info(f"Тег '{tag}' добавлен к директории {directory_id}.")
			return True

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при добавлении тега '{tag}' к директории {directory_id}: {e}", exc_info=True)
		return False
	except Exception as e:
		logger.error(f"Неожиданная ошибка при добавлении тега '{tag}' к директории {directory_id}: {e}", exc_info=True)
		return False

async def remove_tag_from_directory(owner_telegram_id: int, directory_id: int, tag: str) -> bool:
	"""
	Удаляет тег из директории.
	:param owner_telegram_id: Telegram ID владельца директории.
	:param directory_id: ID директории.
	:param tag: Тег для удаления.
	:return: True, если успешно, иначе False.
	"""
	try:
		async with LocalSession() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				logger.warning(f"Пользователь с telegram_id={owner_telegram_id} не найден.")
				return False

			# Найти директорию, принадлежащую этому пользователю
			stmt_dir = select(Directory).where(Directory.id == directory_id, Directory.owner_id == user.id)
			result_dir = await session.execute(stmt_dir)
			directory = result_dir.scalar_one_or_none()

			if not directory:
				logger.warning(f"Директория с ID={directory_id} не найдена или не принадлежит пользователю {owner_telegram_id}.")
				return False

			# Найти тег для удаления
			stmt_tag = select(DirectoryTag).where(
				DirectoryTag.directory_id == directory_id,
				DirectoryTag.tag == tag
			)
			result_tag = await session.execute(stmt_tag)
			tag_to_remove = result_tag.scalar_one_or_none()

			if not tag_to_remove:
				logger.info(f"Тег '{tag}' не найден для директории {directory_id}.")
				return False # Считаем, что операция не успешна, если тега нет

			# Удалить тег
			await session.delete(tag_to_remove)
			await session.commit()
			logger.info(f"Тег '{tag}' удален из директории {directory_id}.")
			return True

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при удалении тега '{tag}' из директории {directory_id}: {e}", exc_info=True)
		return False
	except Exception as e:
		logger.error(f"Неожиданная ошибка при удалении тега '{tag}' из директории {directory_id}: {e}", exc_info=True)
		return False

async def get_directory_tags(owner_telegram_id: int, directory_id: int) -> List[str]:
	"""
	Получает список тегов директории.
	:param owner_telegram_id: Telegram ID владельца директории.
	:param directory_id: ID директории.
	:return: Список тегов.
	"""
	try:
		async with LocalSession() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				logger.warning(f"Пользователь с telegram_id={owner_telegram_id} не найден.")
				return []

			# Найти директорию, принадлежащую этому пользователю
			stmt_dir = select(Directory).where(Directory.id == directory_id, Directory.owner_id == user.id)
			result_dir = await session.execute(stmt_dir)
			directory = result_dir.scalar_one_or_none()

			if not directory:
				logger.warning(f"Директория с ID={directory_id} не найдена или не принадлежит пользователю {owner_telegram_id}.")
				return []

			# Получить теги
			stmt_tags = select(DirectoryTag.tag).where(DirectoryTag.directory_id == directory_id)
			result_tags = await session.execute(stmt_tags)
			tags = [row[0] for row in result_tags.fetchall()] # row[0] потому что выбираем только одно поле tag
			logger.info(f"Получены теги для директории {directory_id}: {tags}")
			return tags

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при получении тегов директории {directory_id}: {e}", exc_info=True)
		return []
	except Exception as e:
		logger.error(f"Неожиданная ошибка при получении тегов директории {directory_id}: {e}", exc_info=True)
		return []
	
async def get_user_directories_by_tag(owner_telegram_id: int, tag: str) -> List[Directory]:
	"""
	Получает список директорий пользователя, у которых есть указанный тег.
	:param owner_telegram_id: Telegram ID владельца.
	:param tag: Тег для фильтрации.
	:return: Список объектов Directory.
	"""
	try:
		async with LocalSession() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				logger.warning(f"Пользователь с telegram_id={owner_telegram_id} не найден.")
				return []

			# Найти директории пользователя, у которых есть тег
			# Это требует JOIN между Directory и DirectoryTag
			stmt_dirs = (
				select(Directory)
				.join(DirectoryTag, Directory.id == DirectoryTag.directory_id)
				.where(Directory.owner_id == user.id, DirectoryTag.tag == tag)
			)
			result_dirs = await session.execute(stmt_dirs)
			directories = list(result_dirs.scalars().all())
			logger.info(f"Найдено {len(directories)} директорий с тегом '{tag}' для пользователя {owner_telegram_id}.")
			return directories

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при фильтрации директорий по тегу '{tag}' для {owner_telegram_id}: {e}", exc_info=True)
		return []
	except Exception as e:
		logger.error(f"Неожиданная ошибка при фильтрации директорий по тегу '{tag}' для {owner_telegram_id}: {e}", exc_info=True)
		return []