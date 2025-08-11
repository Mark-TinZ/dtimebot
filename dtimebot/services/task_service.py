from typing import List
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from dtimebot.database import get_session
from dtimebot.models.tasks import Task, TaskTag
from dtimebot.models.users import User
from dtimebot.models.directories import Directory
from dtimebot.logs import main_logger

logger = main_logger.getChild('task_service')

async def create_task(telegram_id: int, title: str, description: str | None = None, directory_id: int | None = None, time_start: datetime | None = None, time_end: datetime | None = None, embed=None) -> Task | None:
    """
    Создать задачу. Если directory_id не передан — использовать self-директорию пользователя.
    """
    try:
        async with get_session() as session:
            # Получаем user
            stmt_user = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt_user)
            user = res.scalar_one_or_none()
            if user is None:
                logger.warning("User not found when creating task for telegram_id=%s", telegram_id)
                return None

            # Если directory_id не указан — найти self
            if directory_id is None:
                stmt_dir = select(Directory).where(Directory.owner_id == user.id, Directory.is_self == True)
                res2 = await session.execute(stmt_dir)
                self_dir = res2.scalar_one_or_none()
                if self_dir is None:
                    # создаём self-директорию автоматически
                    from dtimebot.services.directory_service import create_directory
                    self_dir = await create_directory(telegram_id=telegram_id, name='Моя директория', description='Личная директория', owner_user=user, is_self=True)
                    if self_dir is None:
                        logger.error("Failed to create self directory for user %s", telegram_id)
                        return None
                directory_id = self_dir.id

            # Убедимся, что указанная директория принадлежит пользователю или доступна
            stmt_check = select(Directory).where(Directory.id == directory_id)
            res_check = await session.execute(stmt_check)
            directory = res_check.scalar_one_or_none()
            if directory is None:
                logger.warning("Directory not found id=%s when creating task", directory_id)
                return None

            task = Task(
                owner_id=user.id,
                directory_id=directory_id,
                title=title,
                description=description,
                time_start=time_start or datetime.utcnow(),
                time_end=time_end,
                embed=embed
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            logger.info("Task created id=%s owner=%s directory=%s", task.id, user.telegram_id, directory_id)
            return task
    except SQLAlchemyError as e:
        logger.exception("Unexpected error while creating task for %s: %s", telegram_id, e)
        return None


async def get_user_tasks(telegram_id: int, directory_id: int | None = None) -> list[Task]:
    try:
        async with get_session() as session:
            # Получаем user
            stmt_user = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt_user)
            user = res.scalar_one_or_none()
            if user is None:
                return []

            # Получаем задачи, где пользователь является владельцем
            stmt_owned_tasks = select(Task).where(Task.owner_id == user.id)
            if directory_id:
                stmt_owned_tasks = stmt_owned_tasks.where(Task.directory_id == directory_id)
            
            res_owned_tasks = await session.execute(stmt_owned_tasks)
            owned_tasks = list(res_owned_tasks.scalars().all())

            # Получаем задачи в директориях, где пользователь является участником
            from dtimebot.models.members import Member
            stmt_member_tasks = (
                select(Task)
                .join(Member, Member.directory_id == Task.directory_id)
                .where(
                    Member.user_id == user.id,
                    Member.is_active == True,
                    Task.owner_id != user.id  # Исключаем задачи, которые пользователь уже видит как владелец
                )
            )
            if directory_id:
                stmt_member_tasks = stmt_member_tasks.where(Task.directory_id == directory_id)
            
            res_member_tasks = await session.execute(stmt_member_tasks)
            member_tasks = list(res_member_tasks.scalars().all())

            # Объединяем и убираем дубли
            all_tasks = owned_tasks + member_tasks
            unique_tasks = {}
            for task in all_tasks:
                unique_tasks[task.id] = task
            
            return list(unique_tasks.values())
    except SQLAlchemyError as e:
        logger.exception("Unexpected error while retrieving tasks for %s: %s", telegram_id, e)
        return []

async def delete_task(owner_telegram_id: int, task_id: int) -> bool:
	"""
	Удаляет задачу пользователя по ID.
	:param owner_telegram_id: Telegram ID владельца.
	:param task_id: ID задачи.
	:return: True, если успешно удалено, иначе False.
	"""
	try:
		async with get_session() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				logger.warning(f"User with telegram_id={owner_telegram_id} not found.")
				return False

			# Найти задачу, принадлежащую этому пользователю
			stmt_task = select(Task).where(Task.id == task_id, Task.owner_id == user.id)
			result_task = await session.execute(stmt_task)
			task = result_task.scalar_one_or_none()

			if not task:
				logger.warning(f"Task with ID={task_id} not found or does not belong to user {owner_telegram_id}.")
				return False

			# Удалить задачу
			await session.delete(task)
			await session.commit()
			logger.info(f"Task '{task.title}' (ID: {task_id}) deleted by user {owner_telegram_id}.")
			return True

	except SQLAlchemyError as e:
		logger.error(f"SQLAlchemy error while deleting task {task_id} for {owner_telegram_id}: {e}", exc_info=True)
		return False
	except Exception as e:
		logger.error(f"Unexpected error while deleting task {task_id} for {owner_telegram_id}: {e}", exc_info=True)
		return False

async def add_tag_to_task(owner_telegram_id: int, task_id: int, tag: str) -> bool:
	"""
	Добавляет тег к задаче.
	:param owner_telegram_id: Telegram ID пользователя (владельца задачи или участника директории).
	:param task_id: ID задачи.
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
				logger.warning(f"User with telegram_id={owner_telegram_id} not found.")
				return False

			# Найти задачу с проверкой прав доступа (владелец задачи или участник директории)
			from dtimebot.models.members import Member
			stmt_task = (
				select(Task)
				.outerjoin(Member, (Member.directory_id == Task.directory_id) & (Member.user_id == user.id) & (Member.is_active == True))
				.where(
					(Task.id == task_id) & 
					((Task.owner_id == user.id) | (Member.user_id == user.id))
				)
			)
			result_task = await session.execute(stmt_task)
			task = result_task.scalar_one_or_none()

			if not task:
				logger.warning(f"Task with ID={task_id} not found or user {owner_telegram_id} does not have access to it.")
				return False

			# Проверить, существует ли уже такой тег
			stmt_tag_check = select(TaskTag).where(
				TaskTag.task_id == task_id,
				TaskTag.tag == tag
			)
			result_tag_check = await session.execute(stmt_tag_check)
			existing_tag = result_tag_check.scalar_one_or_none()

			if existing_tag:
				logger.info(f"Tag '{tag}' already exists for task {task_id}.")
				return True

			# Добавить тег
			new_tag = TaskTag(task_id=task_id, tag=tag)
			session.add(new_tag)
			await session.commit()
			logger.info(f"Tag '{tag}' added to task {task_id}.")
			return True

	except SQLAlchemyError as e:
		logger.error(f"SQLAlchemy error while adding tag '{tag}' to task {task_id}: {e}", exc_info=True)
		return False
	except Exception as e:
		logger.error(f"Unexpected error while adding tag '{tag}' to task {task_id}: {e}", exc_info=True)
		return False

async def remove_tag_from_task(owner_telegram_id: int, task_id: int, tag: str) -> bool:
	"""
	Удаляет тег из задачи.
	:param owner_telegram_id: Telegram ID пользователя (владельца задачи или участника директории).
	:param task_id: ID задачи.
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
				logger.warning(f"User with telegram_id={owner_telegram_id} not found.")
				return False

			# Найти задачу с проверкой прав доступа (владелец задачи или участник директории)
			from dtimebot.models.members import Member
			stmt_task = (
				select(Task)
				.outerjoin(Member, (Member.directory_id == Task.directory_id) & (Member.user_id == user.id) & (Member.is_active == True))
				.where(
					(Task.id == task_id) & 
					((Task.owner_id == user.id) | (Member.user_id == user.id))
				)
			)
			result_task = await session.execute(stmt_task)
			task = result_task.scalar_one_or_none()

			if not task:
				logger.warning(f"Task with ID={task_id} not found or user {owner_telegram_id} does not have access to it.")
				return False

			# Найти тег для удаления
			stmt_tag = select(TaskTag).where(
				TaskTag.task_id == task_id,
				TaskTag.tag == tag
			)
			result_tag = await session.execute(stmt_tag)
			tag_to_remove = result_tag.scalar_one_or_none()

			if not tag_to_remove:
				logger.info(f"Tag '{tag}' not found for task {task_id}.")
				return False

			# Удалить тег
			await session.delete(tag_to_remove)
			await session.commit()
			logger.info(f"Tag '{tag}' removed from task {task_id}.")
			return True

	except SQLAlchemyError as e:
		logger.error(f"SQLAlchemy error while removing tag '{tag}' from task {task_id}: {e}", exc_info=True)
		return False
	except Exception as e:
		logger.error(f"Unexpected error while removing tag '{tag}' from task {task_id}: {e}", exc_info=True)
		return False

async def get_task_tags(owner_telegram_id: int, task_id: int) -> List[str]:
	"""
	Получает список тегов задачи.
	:param owner_telegram_id: Telegram ID пользователя (владельца задачи или участника директории).
	:param task_id: ID задачи.
	:return: Список тегов.
	"""
	try:
		async with get_session() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				logger.warning(f"User with telegram_id={owner_telegram_id} not found.")
				return []

			# Найти задачу с проверкой прав доступа (владелец задачи или участник директории)
			from dtimebot.models.members import Member
			stmt_task = (
				select(Task)
				.outerjoin(Member, (Member.directory_id == Task.directory_id) & (Member.user_id == user.id) & (Member.is_active == True))
				.where(
					(Task.id == task_id) & 
					((Task.owner_id == user.id) | (Member.user_id == user.id))
				)
			)
			result_task = await session.execute(stmt_task)
			task = result_task.scalar_one_or_none()

			if not task:
				logger.warning(f"Task with ID={task_id} not found or user {owner_telegram_id} does not have access to it.")
				return []

			# Получить теги
			stmt_tags = select(TaskTag.tag).where(TaskTag.task_id == task_id)
			result_tags = await session.execute(stmt_tags)
			tags = [row[0] for row in result_tags.fetchall()]
			logger.info(f"Tags retrieved for task {task_id}: {tags}")
			return tags

	except SQLAlchemyError as e:
		logger.error(f"SQLAlchemy error while retrieving tags for task {task_id}: {e}", exc_info=True)
		return []
	except Exception as e:
		logger.error(f"Unexpected error while retrieving tags for task {task_id}: {e}", exc_info=True)
		return []
	
async def get_user_tasks_by_tag(owner_telegram_id: int, tag: str) -> List[Task]:
	"""
	Получает список задач пользователя, у которых есть указанный тег.
	:param owner_telegram_id: Telegram ID пользователя (владельца задачи или участника директории).
	:param tag: Тег для фильтрации.
	:return: Список объектов Task.
	"""
	try:
		async with get_session() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				logger.warning(f"User with telegram_id={owner_telegram_id} not found.")
				return []

			# Найти задачи пользователя (владельца или участника директории), у которых есть тег
			from dtimebot.models.members import Member
			stmt_tasks = (
				select(Task)
				.join(TaskTag, Task.id == TaskTag.task_id)
				.outerjoin(Member, (Member.directory_id == Task.directory_id) & (Member.user_id == user.id) & (Member.is_active == True))
				.where(
					TaskTag.tag == tag,
					((Task.owner_id == user.id) | (Member.user_id == user.id))
				)
			)
			result_tasks = await session.execute(stmt_tasks)
			tasks = list(result_tasks.scalars().all())
			
			# Убираем дубли
			unique_tasks = {}
			for task in tasks:
				unique_tasks[task.id] = task
			
			logger.info(f"Found {len(unique_tasks)} tasks with tag '{tag}' for user {owner_telegram_id}.")
			return list(unique_tasks.values())

	except SQLAlchemyError as e:
		logger.error(f"SQLAlchemy error while filtering tasks by tag '{tag}' for user {owner_telegram_id}: {e}", exc_info=True)
		return []
	except Exception as e:
		logger.error(f"Unexpected error while filtering tasks by tag '{tag}' for user {owner_telegram_id}: {e}", exc_info=True)
		return []

async def update_task(
	owner_telegram_id: int, 
	task_id: int, 
	title: str = None, 
	description: str = None,
	time_start: datetime = None,
	time_end: datetime = None
) -> bool:
	"""
	Обновляет информацию о задаче.
	:param owner_telegram_id: Telegram ID пользователя (владельца задачи или участника директории).
	:param task_id: ID задачи.
	:param title: Новое название (None = не изменять).
	:param description: Новое описание (None = не изменять).
	:param time_start: Новое время начала (None = не изменять).
	:param time_end: Новое время окончания (None = не изменять).
	:return: True, если успешно, иначе False.
	"""
	try:
		async with get_session() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				logger.warning(f"User with telegram_id={owner_telegram_id} not found.")
				return False

			# Найти задачу с проверкой прав доступа (владелец задачи или участник директории)
			from dtimebot.models.members import Member
			stmt_task = (
				select(Task)
				.outerjoin(Member, (Member.directory_id == Task.directory_id) & (Member.user_id == user.id) & (Member.is_active == True))
				.where(
					(Task.id == task_id) & 
					((Task.owner_id == user.id) | (Member.user_id == user.id))
				)
			)
			result_task = await session.execute(stmt_task)
			task = result_task.scalar_one_or_none()

			if not task:
				logger.warning(f"Task with ID={task_id} not found or user {owner_telegram_id} does not have access to it.")
				return False

			# Обновляем поля
			if title is not None:
				task.title = title
			if description is not None:
				task.description = description
			if time_start is not None:
				task.time_start = time_start
			if time_end is not None:
				task.time_end = time_end

			await session.commit()
			logger.info(f"Task {task_id} updated by user {owner_telegram_id}.")
			return True

	except SQLAlchemyError as e:
		logger.error(f"SQLAlchemy error while updating task {task_id}: {e}", exc_info=True)
		return False
	except Exception as e:
		logger.error(f"Unexpected error while updating task {task_id}: {e}", exc_info=True)
		return False

async def get_task_by_id(owner_telegram_id: int, task_id: int) -> Task | None:
	"""
	Получает задачу по ID с проверкой прав доступа.
	:param owner_telegram_id: Telegram ID пользователя (владельца задачи или участника директории).
	:param task_id: ID задачи.
	:return: Объект Task или None.
	"""
	try:
		async with get_session() as session:
			# Найти пользователя
			stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
			result_user = await session.execute(stmt_user)
			user = result_user.scalar_one_or_none()

			if not user:
				return None

			# Найти задачу с проверкой прав доступа (владелец задачи или участник директории)
			from dtimebot.models.members import Member
			stmt_task = (
				select(Task)
				.outerjoin(Member, (Member.directory_id == Task.directory_id) & (Member.user_id == user.id) & (Member.is_active == True))
				.where(
					(Task.id == task_id) & 
					((Task.owner_id == user.id) | (Member.user_id == user.id))
				)
			)
			result_task = await session.execute(stmt_task)
			task = result_task.scalar_one_or_none()

			return task

	except SQLAlchemyError as e:
		logger.error(f"SQLAlchemy error while getting task {task_id}: {e}", exc_info=True)
		return None
	except Exception as e:
		logger.error(f"Unexpected error while getting task {task_id}: {e}", exc_info=True)
		return None