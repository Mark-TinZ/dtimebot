from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from dtimebot.database import get_session
from dtimebot.models.users import User
from dtimebot.logs import main_logger
from dtimebot.services.directory_service import create_directory

logger = main_logger.getChild('user_service')

async def get_or_create_user(tg_user) -> User | None:
    """
    tg_user — объект aiogram.from_user (или подобный), должен иметь id, first_name, username и т.д.
    """
    try:
        async with get_session() as session:
            stmt = select(User).where(User.telegram_id == tg_user.id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                return user

            user = User(
                telegram_id=tg_user.id
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            logger.info("Creating a new user with telegram_id=%s", tg_user.id)

            # Создаём личную директорию (self) для пользователя
            await create_directory(telegram_id=tg_user.id, name='Моя директория', description='Личная директория', owner_user=user, is_self=True)

            return user
    except SQLAlchemyError as e:
        logger.exception("Error creating/getting user %s: %s", getattr(tg_user, 'id', 'unknown'), e)
        return None