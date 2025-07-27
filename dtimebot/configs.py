import yaml
from pathlib import Path
from typing import Optional

from dtimebot.logs import main_logger


logger = main_logger.getChild('configs')

CONFIG_PATH = Path('data/config.yml')
main_config: Optional[dict] = None

def load_configs():
	global main_config

	logger.info('Loading main config...')

	try:
		with open(CONFIG_PATH, 'r') as f:
			config = yaml.safe_load(f)
		if not isinstance(config, dict):
			raise ValueError('Config root node should be a dictionary')
		main_config = config
	except Exception as e:
		logger.error('Failed to load main config', exc_info=e)
		raise

	logger.info('Main config loaded')

def get(name: str):
	if main_config is None:
		raise RuntimeError('Main config is not loaded yet')
	
	try:
		data = main_config[name]
		return data
	except KeyError:
		logger.error(f'Main config partition "{name}" is missing')
		raise
