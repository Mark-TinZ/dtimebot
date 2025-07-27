from asyncio import Task
import asyncio
from pydantic import BaseModel
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart

from dtimebot import configs
from dtimebot.logs import main_logger


logger = main_logger.getChild('bot')

class BotConfig(BaseModel):
	token: str

config: Optional[BotConfig] = None

main_bot: Optional[Bot] = None
dp = Dispatcher()
polling_task: Optional[Task] = None

@dp.message(CommandStart())
async def on_hello(message: Message):
	await message.answer("Hello!")

async def start():
	global config, main_bot, dp, polling_task
	logger.info("Starting aiogram bot...")

	config = BotConfig.model_validate(configs.get('bot'))

	main_bot = Bot(token=config.token)
	await main_bot.delete_webhook(drop_pending_updates=True)

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
