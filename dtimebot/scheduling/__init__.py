from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from pydantic import BaseModel

from dtimebot.logs import main_logger
from dtimebot import configs


logger = main_logger.getChild('scheduling')


class SchedulingConfig(BaseModel):
	# Define scheduling config fields as needed, e.g.:
	timezone: str = "UTC"

config: Optional[SchedulingConfig] = None


scheduler = AsyncIOScheduler(
	logger=logger.getChild('apscheduler'),
	executors={
		'default': AsyncIOExecutor()
	}
)

def start():
	global config
	logger.info('Starting scheduler...')
	config = SchedulingConfig.model_validate(configs.get('scheduling'))

	scheduler.start()
	logger.info('Scheduler started')

def stop():
	logger.info('Stopping scheduler...')
	scheduler.shutdown()
	logger.info('Scheduler stopped')
