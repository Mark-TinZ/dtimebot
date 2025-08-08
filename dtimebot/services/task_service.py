# dtimebot/services/task_service.py
"""
Сервис для работы с задачами.
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from dtimebot.database import LocalSession
from dtimebot.models.tasks import Task
from dtimebot.models.users import User
from dtimebot.models.directories import Directory
from dtimebot.models.activities import ActivityEmbed
from dtimebot.logs import main_logger
from dtimebot.models.activities import ActivityTag

logger = main_logger.getChild('task_service')

async def create_task(
	owner_telegram_id: int,
	title: str,
	description: str = "",
	time_start: datetime = None,
	time_end: datetime = None,
	directory_id: int = None
) -> Optional[Task]:
	"""
	Создает новую задачу для пользователя.
	:param owner_telegram_id: Telegram ID владельца.
	:param title: Название задачи.
	:param description: Описание задачи.
	:param time_start: Время начала.
	:param time_end: Время окончания.
	:param directory_id: ID директории (если задача принадлежит директории).
	:return: Объект Task или None в случае ошибки.
	"""
	try:
		async with LocalSession() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				logger.warning(f"Пользователь с telegram_id={owner_telegram_id} не найден.")
				return None

			# Проверить, существует ли директория, если указана
			dir_obj = None
			if directory_id:
				stmt_dir = select(Directory).where(Directory.id == directory_id, Directory.owner_id == user.id)
				result_dir = await session.execute(stmt_dir)
				dir_obj = result_dir.scalar_one_or_none()
				if not dir_obj:
					logger.warning(f"Директория с ID={directory_id} не найдена или не принадлежит пользователю {owner_telegram_id}.")
					# Можно либо вернуть ошибку, либо создать задачу без директории
					# Здесь мы просто логируем и продолжаем без директории
					directory_id = None # Игнорируем невалидную директорию

			# Создать задачу
			# Для embed используем заглушку, так как модель ActivityEmbed требует 'location'
			embed_data = ActivityEmbed(location="default_location")
			
			new_task = Task(
				owner_id=user.id,
				title=title,
				description=description,
				time_start=time_start or datetime.utcnow(),
				time_end=time_end,
				embed=embed_data # Передаем объект Pydantic
			)
			session.add(new_task)
			await session.commit()
			await session.refresh(new_task)
			logger.info(f"Создана задача '{title}' (ID: {new_task.id}) для пользователя {owner_telegram_id}.")
			return new_task

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при создании задачи для {owner_telegram_id}: {e}", exc_info=True)
		return None
	except Exception as e:
		logger.error(f"Неожиданная ошибка при создании задачи для {owner_telegram_id}: {e}", exc_info=True)
		return None

async def get_user_tasks(owner_telegram_id: int, directory_id: int = None) -> List[Task]:
	"""
	Получает список задач пользователя.
	:param owner_telegram_id: Telegram ID владельца.
	:param directory_id: Опционально, фильтр по ID директории.
	:return: Список объектов Task.
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

			# Построить запрос
			stmt_tasks = select(Task).where(Task.owner_id == user.id)
			if directory_id:
					# Фильтрация по директории будет реализована позже, когда будет связь между задачами и директориями
					# Сейчас задачи не привязаны к директориям напрямую в модели. Это нужно будет добавить.
					# Пока просто логируем.
					logger.info(f"Фильтрация задач по директории ID={directory_id} не реализована в текущей модели.")

			result_tasks = await session.execute(stmt_tasks)
			tasks = list(result_tasks.scalars().all())
			logger.info(f"Найдено {len(tasks)} задач для пользователя {owner_telegram_id}.")
			return tasks

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при получении задач для {owner_telegram_id}: {e}", exc_info=True)
		return []
	except Exception as e:
		logger.error(f"Неожиданная ошибка при получении задач для {owner_telegram_id}: {e}", exc_info=True)
		return []

async def delete_task(owner_telegram_id: int, task_id: int) -> bool:
	"""
	Удаляет задачу пользователя по ID.
	:param owner_telegram_id: Telegram ID владельца.
	:param task_id: ID задачи.
	:return: True, если успешно удалено, иначе False.
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

			# Найти задачу, принадлежащую этому пользователю
			stmt_task = select(Task).where(Task.id == task_id, Task.owner_id == user.id)
			result_task = await session.execute(stmt_task)
			task = result_task.scalar_one_or_none()

			if not task:
				logger.warning(f"Задача с ID={task_id} не найдена или не принадлежит пользователю {owner_telegram_id}.")
				return False

			# Удалить задачу
			await session.delete(task)
			await session.commit()
			logger.info(f"Задача '{task.title}' (ID: {task_id}) удалена пользователем {owner_telegram_id}.")
			return True

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при удалении задачи {task_id} для {owner_telegram_id}: {e}", exc_info=True)
		return False
	except Exception as e:
		logger.error(f"Неожиданная ошибка при удалении задачи {task_id} для {owner_telegram_id}: {e}", exc_info=True)
		return False

async def add_tag_to_task(owner_telegram_id: int, task_id: int, tag: str) -> bool:
	"""
	Добавляет тег к задаче.
	:param owner_telegram_id: Telegram ID владельца задачи.
	:param task_id: ID задачи.
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

			# Найти задачу, принадлежащую этому пользователю
			# Предполагаем, что Task.id соответствует Activity.id
			stmt_task = select(Task).where(Task.id == task_id, Task.owner_id == user.id)
			result_task = await session.execute(stmt_task)
			task = result_task.scalar_one_or_none()

			if not task:
				logger.warning(f"Задача с ID={task_id} не найдена или не принадлежит пользователю {owner_telegram_id}.")
				return False

			# Проверить, существует ли уже такой тег
			stmt_tag_check = select(ActivityTag).where(
				ActivityTag.activity_id == task_id, # activity_id == task_id
				ActivityTag.tag == tag
			)
			result_tag_check = await session.execute(stmt_tag_check)
			existing_tag = result_tag_check.scalar_one_or_none()

			if existing_tag:
				logger.info(f"Тег '{tag}' уже существует для задачи {task_id}.")
				return True

			# Добавить тег
			new_tag = ActivityTag(activity_id=task_id, tag=tag) # Используем ActivityTag
			session.add(new_tag)
			await session.commit()
			logger.info(f"Тег '{tag}' добавлен к задаче {task_id}.")
			return True

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при добавлении тега '{tag}' к задаче {task_id}: {e}", exc_info=True)
		return False
	except Exception as e:
		logger.error(f"Неожиданная ошибка при добавлении тега '{tag}' к задаче {task_id}: {e}", exc_info=True)
		return False

async def remove_tag_from_task(owner_telegram_id: int, task_id: int, tag: str) -> bool:
	"""
	Удаляет тег из задачи.
	:param owner_telegram_id: Telegram ID владельца задачи.
	:param task_id: ID задачи.
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

			# Найти задачу, принадлежащую этому пользователю
			stmt_task = select(Task).where(Task.id == task_id, Task.owner_id == user.id)
			result_task = await session.execute(stmt_task)
			task = result_task.scalar_one_or_none()

			if not task:
				logger.warning(f"Задача с ID={task_id} не найдена или не принадлежит пользователю {owner_telegram_id}.")
				return False

			# Найти тег для удаления
			stmt_tag = select(ActivityTag).where(
				ActivityTag.activity_id == task_id,
				ActivityTag.tag == tag
			)
			result_tag = await session.execute(stmt_tag)
			tag_to_remove = result_tag.scalar_one_or_none()

			if not tag_to_remove:
				logger.info(f"Тег '{tag}' не найден для задачи {task_id}.")
				return False

			# Удалить тег
			await session.delete(tag_to_remove)
			await session.commit()
			logger.info(f"Тег '{tag}' удален из задачи {task_id}.")
			return True

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при удалении тега '{tag}' из задачи {task_id}: {e}", exc_info=True)
		return False
	except Exception as e:
		logger.error(f"Неожиданная ошибка при удалении тега '{tag}' из задачи {task_id}: {e}", exc_info=True)
		return False

async def get_task_tags(owner_telegram_id: int, task_id: int) -> List[str]:
	"""
	Получает список тегов задачи.
	:param owner_telegram_id: Telegram ID владельца задачи.
	:param task_id: ID задачи.
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

			# Найти задачу, принадлежащую этому пользователю
			stmt_task = select(Task).where(Task.id == task_id, Task.owner_id == user.id)
			result_task = await session.execute(stmt_task)
			task = result_task.scalar_one_or_none()

			if not task:
				logger.warning(f"Задача с ID={task_id} не найдена или не принадлежит пользователю {owner_telegram_id}.")
				return []

			# Получить теги
			stmt_tags = select(ActivityTag.tag).where(ActivityTag.activity_id == task_id)
			result_tags = await session.execute(stmt_tags)
			tags = [row[0] for row in result_tags.fetchall()]
			logger.info(f"Получены теги для задачи {task_id}: {tags}")
			return tags

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при получении тегов задачи {task_id}: {e}", exc_info=True)
		return []
	except Exception as e:
		logger.error(f"Неожиданная ошибка при получении тегов задачи {task_id}: {e}", exc_info=True)
		return []
	
async def get_user_tasks_by_tag(owner_telegram_id: int, tag: str) -> List[Task]:
	"""
	Получает список задач пользователя, у которых есть указанный тег.
	:param owner_telegram_id: Telegram ID владельца.
	:param tag: Тег для фильтрации.
	:return: Список объектов Task.
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

			# Найти задачи пользователя, у которых есть тег
			# JOIN между Task (как Activity) и ActivityTag
			stmt_tasks = (
				select(Task)
				.join(ActivityTag, Task.id == ActivityTag.activity_id)
				.where(Task.owner_id == user.id, ActivityTag.tag == tag)
			)
			result_tasks = await session.execute(stmt_tasks)
			tasks = list(result_tasks.scalars().all())
			logger.info(f"Найдено {len(tasks)} задач с тегом '{tag}' для пользователя {owner_telegram_id}.")
			return tasks

	except SQLAlchemyError as e:
		logger.error(f"Ошибка SQLAlchemy при фильтрации задач по тегу '{tag}' для {owner_telegram_id}: {e}", exc_info=True)
		return []
	except Exception as e:
		logger.error(f"Неожиданная ошибка при фильтрации задач по тегу '{tag}' для {owner_telegram_id}: {e}", exc_info=True)
		return []