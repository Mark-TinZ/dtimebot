from dtimebot.logs import main_logger
from dtimebot import configs, scheduling, bot, database

async def start():
	main_logger.info("Starting dtimebot...")
	configs.load_configs()
	scheduling.start()
	await database.start()
	await database.update_models()
	await bot.start()
	main_logger.info("dtimebot started")

async def stop():
	main_logger.info("Stopping dtimebot...")
	await bot.stop()
	scheduling.stop()
	main_logger.info("dtimebot stopped")
