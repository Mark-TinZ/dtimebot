from typing import Optional, AsyncGenerator
from pydantic import BaseModel
from sqlalchemy import Text, TypeDecorator, JSON
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from contextlib import asynccontextmanager

from dtimebot import configs
from dtimebot.logs import main_logger

class DatabaseConfig(BaseModel):
    url: str

config: Optional[DatabaseConfig] = None

logger = main_logger.getChild('database')

engine: Optional[AsyncEngine] = None
LocalSession: Optional[async_sessionmaker[AsyncSession]] = None

Base = declarative_base()


async def start() -> None:
    """
    Инициализация подключения к БД. Должна вызываться до старта бота.
    """
    global config, engine, LocalSession
    logger.info('Starting database...')

    config = DatabaseConfig.model_validate(configs.get('database'))

    logger.info('Initializing engine...')
    engine = create_async_engine(
        url=config.url,
        future=True
    )
    logger.info('Engine initialized')

    logger.info('Initializing async session maker...')
    LocalSession = async_sessionmaker(engine, expire_on_commit=False)
    logger.info('Session maker initialized')

    logger.info('Database started')


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Асинхронный контекст-менеджер для получения сессии.
    Используйте: `async with get_session() as session:`
    """
    global LocalSession
    if LocalSession is None:
        raise RuntimeError('Database session maker is not initialized. Call dtimebot.database.start() first.')
    async with LocalSession() as session:
        yield session


async def update_models() -> None:
    logger.info('Updating models...')
    global Base, engine

    if engine is None:
        raise RuntimeError('Engine is not initialized. Call dtimebot.database.start() first.')

    from dtimebot import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info('Models updated')


async def stop() -> None:
    logger.info('Stopping database...')
    if engine is not None:
        await engine.dispose()
    logger.info('Database stopped')


class JSONModel(TypeDecorator):
    impl = JSON

    def __init__(self, pydantic_model: type[BaseModel], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pydantic_model = pydantic_model

    def process_bind_param(self, value: BaseModel | None, dialect):
        return value.model_dump() if value is not None else None

    def process_result_value(self, value: dict | None, dialect):
        return self.pydantic_model.model_validate(value) if value is not None else None


class TextArray(TypeDecorator):
    impl = Text

    unique_set: bool

    def __init__(self, unique_set: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unique_set = unique_set

    def process_bind_param(self, value: list[str] | None, dialect):
        # TODO: Escape ',' chars
        return ','.join(value) if value is not None else None

    def process_result_value(self, value: str | None, dialect):
        if not value:
            return None
        res = value.split(',')
        if self.unique_set:
            res = list(set(res))
        return res
