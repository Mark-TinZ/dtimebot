from asyncio import Task
import asyncio
from pydantic import BaseModel
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart, CommandObject

from dtimebot import configs
from dtimebot.logs import main_logger
from dtimebot.services import user_service

from dtimebot.bot import handlers


logger = main_logger.getChild('bot')

class BotConfig(BaseModel):
	token: str

config: Optional[BotConfig] = None

main_bot: Optional[Bot] = None
dp = Dispatcher()
polling_task: Optional[Task] = None


@dp.message(CommandStart())
async def on_hello(message: Message, command: CommandObject):
	"""
	Обработчик команды /start.
	Регистрирует пользователя, если его еще нет в БД.
	"""
	user_telegram_id = message.from_user.id
	user_full_name = message.from_user.full_name or ""
	user_username = message.from_user.username or ""

	try:
		user = await user_service.get_or_create_user(
			telegram_id=user_telegram_id,
			full_name=user_full_name,
			username=user_username
		)
		greeting_text = (
			f"Привет, {user_full_name}!\n"
			f"Имя пользователя: @{user_username if user_username else 'Не указано'}\n"
			f"Вы успешно зарегистрированы в системе.\n"
			f"Дата регистрации: {user.created_at.strftime('%d.%m.%Y %H:%M:%S') if user.created_at else 'Неизвестно'}\n"
		)
		await message.answer(greeting_text)
	except Exception as e:
		logger.error(f"Ошибка при регистрации пользователя {user_telegram_id}: {e}", exc_info=True)
		await message.answer("Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.")

async def start():
	global config, main_bot, dp, polling_task
	logger.info("Starting aiogram bot...")

	config = BotConfig.model_validate(configs.get('bot'))

	main_bot = Bot(token=config.token)
	await main_bot.delete_webhook(drop_pending_updates=True)

	# Подключаем роутер с обработчиками
	dp.include_router(handlers.router)

	polling_task = asyncio.create_task(dp.start_polling(main_bot))

async def stop():
	global polling_task, main_bot
	logger.info("Stopping aiogram bot...")
	if polling_task:
		polling_task.cancel()
		try:
			await polling_task
		except asyncio.CancelledError:
			logger.info("Polling task cancelled")
		polling_task = None
	if main_bot:
		await main_bot.close()
		main_bot = None
	logger.info("Aiogram bot stopped")