from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from typing import List

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from typing import List

from dtimebot.database import get_session
from dtimebot.models.directories import Directory, DirectoryTag
from dtimebot.models.members import Member
from dtimebot.models.users import User
from dtimebot.logs import main_logger

logger = main_logger.getChild('directory_service')

async def create_directory(telegram_id: int, name: str, description: str | None = None, owner_user: User | None = None, is_self: bool = False) -> Directory | None:
	"""
	Создать директорию. Если owner_user не передан — попытаемся получить пользователя по telegram_id.
	is_self=True — пометить директорию как личную (удалять нельзя).
	"""
	try:
		async with get_session() as session:
			# Получаем/передаём владельца
			if owner_user is None:
				stmt_user = select(User).where(User.telegram_id == telegram_id)
				res = await session.execute(stmt_user)
				owner_user = res.scalar_one_or_none()
				if owner_user is None:
					logger.warning("User not found for telegram_id=%s while creating directory", telegram_id)
					return None

			# Проверка — не создаём дубликат self-директории
			if is_self:
				stmt_check = select(Directory).where(Directory.owner_id == owner_user.id, Directory.is_self == True)
				res = await session.execute(stmt_check)
				existing = res.scalar_one_or_none()
				if existing:
					return existing

			directory = Directory(
				owner_id=owner_user.id,
				name=name,
				description=description,
				is_self=is_self
			)
			session.add(directory)
			await session.commit()
			await session.refresh(directory)

			# Добавим запись в Member (владелец — участник)
			member = Member(directory_id=directory.id, user_id=owner_user.id, is_active=True)
			session.add(member)
			await session.commit()

			logger.info("Directory created id=%s owner=%s is_self=%s", directory.id, owner_user.telegram_id, is_self)
			return directory
	except SQLAlchemyError as e:
		logger.exception("An unexpected error occurred while creating directory for %s: %s", telegram_id, e)
		return None

async def get_user_directories(telegram_id: int) -> list[Directory]:
	"""
	Вернуть все директории, доступные пользователю, по членству (включая свои).
	"""
	try:
		async with get_session() as session:
			# Найдём user.id
			stmt_user = select(User).where(User.telegram_id == telegram_id)
			res = await session.execute(stmt_user)
			user = res.scalar_one_or_none()
			if user is None:
				return []

			# Директории, где пользователь является активным участником (включая владельца)
			stmt = (
				select(Directory)
				.join(Member, Member.directory_id == Directory.id)
				.where(Member.user_id == user.id, Member.is_active == True)
			)
			res = await session.execute(stmt)
			rows = list(res.scalars().all())

			# Убираем дубли по id
			unique_by_id: dict[int, Directory] = {}
			for d in rows:
				unique_by_id[d.id] = d
			return list(unique_by_id.values())
	except SQLAlchemyError as e:
		logger.exception("An unexpected error occurred while retrieving directories for %s: %s", telegram_id, e)
		return []

async def delete_directory(telegram_id: int, directory_id: int) -> bool:
	"""
	Удаление директории — запрещено, если is_self=True. Допускается только владельцу.
	"""
	try:
		async with get_session() as session:
			# Определяем пользователя
			stmt_user = select(User).where(User.telegram_id == telegram_id)
			res_user = await session.execute(stmt_user)
			user = res_user.scalar_one_or_none()
			if user is None:
				return False

			stmt = select(Directory).where(Directory.id == directory_id, Directory.owner_id == user.id)
			res = await session.execute(stmt)
			directory = res.scalar_one_or_none()
			if directory is None:
				return False

			if directory.is_self:
				logger.warning("Attempt to delete self directory id=%s by telegram=%s", directory_id, telegram_id)
				return False

			await session.delete(directory)
			await session.commit()
			return True
	except SQLAlchemyError as e:
		logger.exception("Error deleting directory %s: %s", directory_id, e)
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
		async with get_session() as session:
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
		async with get_session() as session:
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
		async with get_session() as session:
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
		async with get_session() as session:
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

async def update_directory(owner_telegram_id: int, directory_id: int, name: str = None, description: str = None) -> bool:
	"""
	Обновляет информацию о директории.
	:param owner_telegram_id: Telegram ID владельца директории.
	:param directory_id: ID директории.
	:param name: Новое название (None = не изменять).
	:param description: Новое описание (None = не изменять).
	:return: True, если успешно, иначе False.
	"""
	try:
		async with get_session() as session:
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

			# Обновляем поля
			if name is not None:
				directory.name = name
			if description is not None:
				directory.description = description

			await session.commit()
			logger.info(f"Директория {directory_id} обновлена пользователем {owner_telegram_id}.")
			return True

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при обновлении директории {directory_id}: {e}", exc_info=True)
		return False
	except Exception as e:
		logger.error(f"Неожиданная ошибка при обновлении директории {directory_id}: {e}", exc_info=True)
		return False

async def get_directory_by_id(owner_telegram_id: int, directory_id: int) -> Directory | None:
	"""
	Получает директорию по ID с проверкой прав доступа.
	:param owner_telegram_id: Telegram ID владельца.
	:param directory_id: ID директории.
	:return: Объект Directory или None.
	"""
	try:
		async with get_session() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				return None

			# Найти директорию
			stmt_dir = select(Directory).where(Directory.id == directory_id, Directory.owner_id == user.id)
			result_dir = await session.execute(stmt_dir)
			directory = result_dir.scalar_one_or_none()

			return directory
	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при получении директории {directory_id}: {e}", exc_info=True)
		return None
	except Exception as e:
		logger.error(f"Неожиданная ошибка при получении директории {directory_id}: {e}", exc_info=True)
		return None


async def get_owned_directories(telegram_id: int) -> list[Directory]:
	"""
	Вернуть директории, где пользователь является владельцем.
	"""
	try:
		async with get_session() as session:
			stmt_user = select(User).where(User.telegram_id == telegram_id)
			res_user = await session.execute(stmt_user)
			user = res_user.scalar_one_or_none()
			if not user:
				return []

			stmt = select(Directory).where(Directory.owner_id == user.id)
			res = await session.execute(stmt)
			return list(res.scalars().all())
	except SQLAlchemyError as e:
		logger.exception("An unexpected error occurred while retrieving owned directories for %s: %s", telegram_id, e)
		return []