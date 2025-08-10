import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from dtimebot.database import get_session
from dtimebot.models.invitations import Invitation
from dtimebot.models.members import Member
from dtimebot.models.users import User
from dtimebot.models.directories import Directory
from dtimebot.logs import main_logger

logger = main_logger.getChild('invitation_service')

def generate_invitation_code(length: int = 8) -> str:
    """Генерирует случайный код приглашения."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

async def create_invitation(
    owner_telegram_id: int, 
    directory_id: int, 
    max_uses: Optional[int] = None,
    valid_until: Optional[datetime] = None,
    filter_tag: Optional[str] = None
) -> Optional[Invitation]:
    """
    Создает приглашение в директорию.
    
    Args:
        owner_telegram_id: Telegram ID владельца директории
        directory_id: ID директории
        max_uses: Максимальное количество использований (None = без ограничений)
        valid_until: Дата истечения приглашения (None = без ограничений)
        filter_tag: Тег для фильтрации доступа к задачам
    
    Returns:
        Объект приглашения или None при ошибке
    """
    try:
        async with get_session() as session:
            # Проверяем, что пользователь существует и является владельцем директории
            stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
            result_user = await session.execute(stmt_user)
            user = result_user.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User with telegram_id={owner_telegram_id} not found")
                return None
            
            # Проверяем, что директория существует и принадлежит пользователю
            stmt_dir = select(Directory).where(
                Directory.id == directory_id,
                Directory.owner_id == user.id
            )
            result_dir = await session.execute(stmt_dir)
            directory = result_dir.scalar_one_or_none()
            
            if not directory:
                logger.warning(f"Directory {directory_id} not found or not owned by user {owner_telegram_id}")
                return None
            
            # Генерируем уникальный код
            while True:
                code = generate_invitation_code()
                stmt_check = select(Invitation).where(Invitation.code == code)
                result_check = await session.execute(stmt_check)
                if not result_check.scalar_one_or_none():
                    break
            
            # Создаем приглашение
            invitation = Invitation(
                owner_id=user.id,
                directory_id=directory_id,
                code=code,
                max_uses=max_uses,
                valid_until=valid_until,
                filter=filter_tag,
                used_count=0
            )
            
            session.add(invitation)
            await session.commit()
            await session.refresh(invitation)
            
            logger.info(f"Invitation created: code={code}, directory={directory_id}, owner={owner_telegram_id}")
            return invitation
            
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error while creating invitation: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error while creating invitation: {e}", exc_info=True)
        return None

async def join_directory_by_code(telegram_id: int, code: str) -> bool:
    """
    Присоединяет пользователя к директории по коду приглашения.
    
    Args:
        telegram_id: Telegram ID пользователя
        code: Код приглашения
    
    Returns:
        True если успешно присоединился, False в противном случае
    """
    try:
        async with get_session() as session:
            # Находим пользователя
            stmt_user = select(User).where(User.telegram_id == telegram_id)
            result_user = await session.execute(stmt_user)
            user = result_user.scalar_one_or_none()
            
            if not user:
                logger.warning(f"User with telegram_id={telegram_id} not found")
                return False
            
            # Находим приглашение
            stmt_inv = select(Invitation).where(Invitation.code == code)
            result_inv = await session.execute(stmt_inv)
            invitation = result_inv.scalar_one_or_none()
            
            if not invitation:
                logger.warning(f"Invitation with code {code} not found")
                return False
            
            # Проверяем срок действия
            if invitation.valid_until and datetime.utcnow() > invitation.valid_until:
                logger.warning(f"Invitation {code} has expired")
                return False
            
            # Проверяем лимит использований
            if invitation.max_uses and invitation.used_count >= invitation.max_uses:
                logger.warning(f"Invitation {code} has reached usage limit")
                return False
            
            # Проверяем, не является ли пользователь уже участником
            stmt_member = select(Member).where(
                Member.directory_id == invitation.directory_id,
                Member.user_id == user.id,
                Member.is_active == True
            )
            result_member = await session.execute(stmt_member)
            existing_member = result_member.scalar_one_or_none()
            
            if existing_member:
                logger.info(f"User {telegram_id} is already a member of directory")
                return True  # Считаем успехом, если уже участник
            
            # Добавляем пользователя как участника
            member = Member(
                directory_id=invitation.directory_id,
                user_id=user.id,
                invitation_id=invitation.id,
                is_active=True
            )
            
            session.add(member)
            
            # Увеличиваем счетчик использований
            invitation.used_count += 1
            
            await session.commit()
            
            logger.info(f"User {telegram_id} successfully joined directory via invitation {code}")
            return True
            
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error while joining directory: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error while joining directory: {e}", exc_info=True)
        return False

async def get_directory_members(owner_telegram_id: int, directory_id: int) -> List[User]:
    """
    Получает список участников директории.
    
    Args:
        owner_telegram_id: Telegram ID владельца директории
        directory_id: ID директории
    
    Returns:
        Список пользователей-участников
    """
    try:
        async with get_session() as session:
            # Проверяем права доступа
            stmt_owner = select(User).where(User.telegram_id == owner_telegram_id)
            result_owner = await session.execute(stmt_owner)
            owner = result_owner.scalar_one_or_none()
            
            if not owner:
                return []
            
            stmt_dir = select(Directory).where(
                Directory.id == directory_id,
                Directory.owner_id == owner.id
            )
            result_dir = await session.execute(stmt_dir)
            directory = result_dir.scalar_one_or_none()
            
            if not directory:
                return []
            
            # Получаем участников
            stmt_members = (
                select(User)
                .join(Member, User.id == Member.user_id)
                .where(
                    Member.directory_id == directory_id,
                    Member.is_active == True
                )
            )
            result_members = await session.execute(stmt_members)
            members = list(result_members.scalars().all())
            
            return members
            
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error while getting directory members: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Unexpected error while getting directory members: {e}", exc_info=True)
        return []

async def leave_directory(telegram_id: int, directory_id: int) -> bool:
    """
    Покидает директорию.
    
    Args:
        telegram_id: Telegram ID пользователя
        directory_id: ID директории
    
    Returns:
        True если успешно покинул, False в противном случае
    """
    try:
        async with get_session() as session:
            # Находим пользователя
            stmt_user = select(User).where(User.telegram_id == telegram_id)
            result_user = await session.execute(stmt_user)
            user = result_user.scalar_one_or_none()
            
            if not user:
                return False
            
            # Проверяем, что пользователь не является владельцем
            stmt_dir = select(Directory).where(
                Directory.id == directory_id,
                Directory.owner_id == user.id
            )
            result_dir = await session.execute(stmt_dir)
            directory = result_dir.scalar_one_or_none()
            
            if directory:
                logger.warning(f"Owner {telegram_id} cannot leave directory {directory_id}")
                return False
            
            # Находим и деактивируем членство
            stmt_member = select(Member).where(
                Member.directory_id == directory_id,
                Member.user_id == user.id,
                Member.is_active == True
            )
            result_member = await session.execute(stmt_member)
            member = result_member.scalar_one_or_none()
            
            if not member:
                logger.warning(f"User {telegram_id} is not a member of directory {directory_id}")
                return False
            
            member.is_active = False
            member.deleted_at = datetime.utcnow()
            
            await session.commit()
            
            logger.info(f"User {telegram_id} left directory {directory_id}")
            return True
            
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error while leaving directory: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error while leaving directory: {e}", exc_info=True)
        return False

async def get_user_invitations(owner_telegram_id: int) -> List[Invitation]:
    """
    Получает список приглашений пользователя.
    
    Args:
        owner_telegram_id: Telegram ID владельца
    
    Returns:
        Список приглашений
    """
    try:
        async with get_session() as session:
            stmt_user = select(User).where(User.telegram_id == owner_telegram_id)
            result_user = await session.execute(stmt_user)
            user = result_user.scalar_one_or_none()
            
            if not user:
                return []
            
            stmt_inv = select(Invitation).where(Invitation.owner_id == user.id)
            result_inv = await session.execute(stmt_inv)
            invitations = list(result_inv.scalars().all())
            
            return invitations
            
    except SQLAlchemyError as e:
        logger.error(f"SQLAlchemy error while getting user invitations: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Unexpected error while getting user invitations: {e}", exc_info=True)
        return []
