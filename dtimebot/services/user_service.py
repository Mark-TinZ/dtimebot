from typing import TYPE_CHECKING
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
#from sqlalchemy.ext.asyncio import AsyncSession
from dtimebot.database import Base
from dtimebot.models.users import User
from dtimebot.logs import main_logger

if TYPE_CHECKING:
	from sqlalchemy.ext.asyncio import AsyncSession

logger = main_logger.getChild('user_service')

# Функция будет использовать LocalSession, импортируя его внутри функции
async def get_or_create_user(telegram_id: int, full_name: str = "", username: str = "") -> User:
	"""Получает пользователя из БД или создает нового."""
	try:
		# Импортируем LocalSession внутри функции, чтобы избежать проблем с инициализацией
		from dtimebot.database import LocalSession
		
		# Проверяем, что LocalSession не None (на всякий случай)
		if LocalSession is None:
			logger.critical("LocalSession is None. Database might not be initialized properly.")
			raise RuntimeError("Database session is not available.")

		async with LocalSession() as session: # type: ignore
			# Проверяем, существует ли пользователь
			stmt = select(User).where(User.telegram_id == telegram_id)
			result = await session.execute(stmt)
			user = result.scalar_one_or_none()

			if user is None:
				# Создаем нового пользователя
				logger.info(f"Creating a new user with telegram_id={telegram_id}")
				user = User(
					telegram_id=telegram_id,
					# В текущей модели нет полей full_name и username, но можно добавить позже
				)
				session.add(user)
				await session.commit()
				await session.refresh(user) # Обновляем объект, чтобы получить id
				logger.info(f"A user with telegram_id={telegram_id} has been successfully created with ID={user.id}.")
			else:
				logger.info(f"A user with telegram_id={telegram_id} already exists with ID={user.id}.")

			return user
	except SQLAlchemyError as e:
		logger.error(f"SQLAlchemy error occurred while processing user {telegram_id}: {e}", exc_info=True)
		# Можно пробросить исключение выше или вернуть None/дефолтное значение
		raise
	except Exception as e:
		logger.error(f"An unexpected error occurred while processing user {telegram_id}: {e}", exc_info=True)
		raise
