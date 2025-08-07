from asyncio import Task
import asyncio
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart, CommandObject, Command

from aiogram import F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from dtimebot import configs
from dtimebot.logs import main_logger
from dtimebot.models.users import User



logger = main_logger.getChild('bot')

class BotConfig(BaseModel):
	token: str

config: Optional[BotConfig] = None

main_bot: Optional[Bot] = None
dp = Dispatcher()
polling_task: Optional[Task] = None

# --- Определение состояний для FSM ---
class DirectoryStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()

class TaskStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    # Можно добавить шаги для выбора директории, времени и т.д.

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
		# Импортируем user_service внутри функции
		from dtimebot.services import user_service

		user = await user_service.get_or_create_user(
			telegram_id=user_telegram_id,
			full_name=user_full_name,
			username=user_username
		)
		# Формируем приветственное сообщение
		greeting_text = (
			f"Привет, {user_full_name}!\n"
			f"Имя пользователя: @{user_username if user_username else 'Не указано'}\n"
			#f"Ваш Telegram ID: {user_telegram_id}\n"
			f"Вы успешно зарегистрированы в системе.\n"
			f"Дата регистрации: {user.created_at.strftime('%d.%m.%Y %H:%M:%S') if user.created_at else 'Неизвестно'}\n"
		)
		await message.answer(greeting_text)
	except Exception as e:
		logger.error(f"Ошибка при регистрации пользователя {user_telegram_id}: {e}", exc_info=True)
		await message.answer("Произошла ошибка при регистрации. Пожалуйста, попробуйте позже.")

@dp.message(Command("help"))
async def on_help(message: Message):
	"""Обработчик команды /help."""
	help_text = (
		"Я бот для управления задачами и событиями!\n"
		"Доступные команды:\n"
		"/start - Зарегистрироваться/начать работу\n"
		"/help - Показать это сообщение\n"
		"/me - Показать информацию о вас\n"
		"/directories - Показать список ваших директорий (пока не реализовано)\n"
	)
	await message.answer(help_text)

@dp.message(Command("me"))
async def on_me(message: Message):
	"""Обработчик команды /me. Показывает информацию о пользователе."""
	user_telegram_id = message.from_user.id
	user_full_name = message.from_user.full_name or ""
	user_username = message.from_user.username or ""

	try:
		# Импортируем LocalSession внутри функции, чтобы избежать проблем с инициализацией
		from dtimebot.database import LocalSession

		# Проверяем, что LocalSession не None (на всякий случай)
		if LocalSession is None:
			logger.critical("LocalSession is None. Database might not be initialized properly.")
			raise RuntimeError("Database session is not available.")
		
		async with LocalSession() as session: # type: ignore
			# Проверяем, существует ли пользователь
			stmt = select(User).where(User.telegram_id == user_telegram_id)
			result = await session.execute(stmt)
			user = result.scalar_one_or_none()

		if user:
			me_text = (
				f"Ваша информация:\n"
				#f"ID в системе: {user.id}\n"
				#f"Telegram ID: {user.telegram_id}\n"
				f"Полное имя: {user_full_name}\n"
				f"Имя пользователя: @{user_username if user_username else 'Не указано'}\n"
				f"Зарегистрирован: {user.created_at.strftime('%d.%m.%Y %H:%M:%S') if user.created_at else 'Неизвестно'}\n"
			)
			# Проверяем, удален ли пользователь (если поле используется)
			if user.deleted_at:
				me_text += f"Удален: {user.deleted_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
		else:
			me_text = "Вы еще не зарегистрированы. Используйте /start для регистрации."

		await message.answer(me_text)
	except Exception as e:
		logger.error(f"Ошибка при получении информации о пользователе {user_telegram_id}: {e}", exc_info=True)
		await message.answer("Произошла ошибка при получении вашей информации.")

@dp.message(Command("directories"))
async def on_directories(message: Message):
	"""Обработчик команды /directories. Пока заглушка."""
	user_telegram_id = message.from_user.id
	# TODO: Здесь будет логика получения списка директорий пользователя
	await message.answer("Список ваших директорий пока не реализован. Это будет сделано на следующем этапе.")

# --- Команды для работы с директориями ---

@dp.message(Command("create_dir"))
async def cmd_create_dir_start(message: Message, state: FSMContext):
    """Начало создания директории: запрос названия."""
    await message.answer("Введите название новой директории:")
    await state.set_state(DirectoryStates.waiting_for_name)

@dp.message(DirectoryStates.waiting_for_name, F.text)
async def cmd_create_dir_name_received(message: Message, state: FSMContext):
    """Получено название директории, запрос описания."""
    await state.update_data(name=message.text)
    await message.answer("Введите описание директории (или отправьте /skip, чтобы пропустить):")
    await state.set_state(DirectoryStates.waiting_for_description)

@dp.message(DirectoryStates.waiting_for_description, Command("skip"))
async def cmd_create_dir_skip_description(message: Message, state: FSMContext):
    """Пропуск описания и создание директории."""
    user_data = await state.get_data()
    name = user_data['name']
    description = ""
    telegram_id = message.from_user.id

    from dtimebot.services import directory_service
    directory = await directory_service.create_directory(telegram_id, name, description)
    
    if directory:
        await message.answer(f"✅ Директория '<b>{name}</b>' успешно создана! ID: {directory.id}", parse_mode='HTML')
    else:
        await message.answer("❌ Ошибка при создании директории. Попробуйте позже.")
    
    await state.clear()

@dp.message(DirectoryStates.waiting_for_description, F.text)
async def cmd_create_dir_description_received(message: Message, state: FSMContext):
    """Получено описание, создание директории."""
    user_data = await state.get_data()
    name = user_data['name']
    description = message.text
    telegram_id = message.from_user.id

    from dtimebot.services import directory_service
    directory = await directory_service.create_directory(telegram_id, name, description)
    
    if directory:
        await message.answer(f"✅ Директория '<b>{name}</b>' успешно создана! ID: {directory.id}\nОписание: {description}", parse_mode='HTML')
    else:
        await message.answer("❌ Ошибка при создании директории. Попробуйте позже.")
    
    await state.clear()

@dp.message(Command("list_dirs"))
async def cmd_list_dirs(message: Message):
    """Список директорий пользователя."""
    telegram_id = message.from_user.id
    
    from dtimebot.services import directory_service
    directories = await directory_service.get_user_directories(telegram_id)
    
    if not directories:
        await message.answer("📭 У вас пока нет директорий. Создайте первую с помощью /create_dir")
        return

    response_text = "📁 Ваши директории:\n\n"
    for i, dir_obj in enumerate(directories, 1):
        response_text += (
            f"<b>{i}. {dir_obj.name}</b>\n"
            f"   ID: {dir_obj.id}\n"
            f"   Создана: {dir_obj.created_at.strftime('%d.%m.%Y %H:%M') if dir_obj.created_at else 'Неизвестно'}\n"
            f"   Описание: {dir_obj.description or '-'}\n\n"
        )
    
    await message.answer(response_text, parse_mode='HTML')

@dp.message(Command("delete_dir"))
async def cmd_delete_dir_start(message: Message, state: FSMContext):
    """Начало удаления директории: запрос ID."""
    telegram_id = message.from_user.id
    
    from dtimebot.services import directory_service
    directories = await directory_service.get_user_directories(telegram_id)
    
    if not directories:
        await message.answer("📭 У вас нет директорий для удаления.")
        return

    keyboard_buttons = []
    for dir_obj in directories:
        keyboard_buttons.append([f"{dir_obj.id} - {dir_obj.name}"])
    
    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    builder = ReplyKeyboardBuilder()
    for row in keyboard_buttons:
        builder.button(text=row[0])
    builder.button(text="❌ Отмена")
    builder.adjust(1) # Одна кнопка в ряду

    await message.answer(
        "Выберите директорию для удаления (отправьте её ID и название):",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    )
    await state.set_state(DirectoryStates.waiting_for_name) # Переиспользуем состояние для ID

@dp.message(DirectoryStates.waiting_for_name, F.text)
async def cmd_delete_dir_id_received(message: Message, state: FSMContext):
    """Получен ID директории для удаления."""
    text = message.text.strip()
    
    if text.lower() == "❌ отмена":
        await message.answer("❌ Удаление отменено.", reply_markup=None)
        await state.clear()
        return

    try:
        # Пытаемся извлечь ID из текста "ID - Название"
        dir_id_str = text.split(' - ')[0]
        directory_id = int(dir_id_str)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Пожалуйста, выберите директорию из списка или отправьте ID.")
        return

    telegram_id = message.from_user.id
    
    from dtimebot.services import directory_service
    success = await directory_service.delete_directory(telegram_id, directory_id)
    
    if success:
        await message.answer(f"✅ Директория с ID {directory_id} успешно удалена.", reply_markup=None)
    else:
        await message.answer("❌ Ошибка при удалении директории. Возможно, она не существует или не принадлежит вам.", reply_markup=None)
    
    await state.clear()

# --- Команды для работы с задачами ---

@dp.message(Command("create_task"))
async def cmd_create_task_start(message: Message, state: FSMContext):
    """Начало создания задачи: запрос названия."""
    await message.answer("Введите название новой задачи:")
    await state.set_state(TaskStates.waiting_for_title)

@dp.message(TaskStates.waiting_for_title, F.text)
async def cmd_create_task_title_received(message: Message, state: FSMContext):
    """Получено название задачи, запрос описания."""
    await state.update_data(title=message.text)
    await message.answer("Введите описание задачи (или отправьте /skip, чтобы пропустить):")
    await state.set_state(TaskStates.waiting_for_description)

@dp.message(TaskStates.waiting_for_description, Command("skip"))
async def cmd_create_task_skip_description(message: Message, state: FSMContext):
    """Пропуск описания и создание задачи."""
    user_data = await state.get_data()
    title = user_data['title']
    description = ""
    telegram_id = message.from_user.id

    from dtimebot.services import task_service
    task = await task_service.create_task(telegram_id, title, description)
    
    if task:
        await message.answer(f"✅ Задача '<b>{title}</b>' успешно создана! ID: {task.id}", parse_mode='HTML')
    else:
        await message.answer("❌ Ошибка при создании задачи. Попробуйте позже.")
    
    await state.clear()

@dp.message(TaskStates.waiting_for_description, F.text)
async def cmd_create_task_description_received(message: Message, state: FSMContext):
    """Получено описание, создание задачи."""
    user_data = await state.get_data()
    title = user_data['title']
    description = message.text
    telegram_id = message.from_user.id

    from dtimebot.services import task_service
    task = await task_service.create_task(telegram_id, title, description)
    
    if task:
        await message.answer(f"✅ Задача '<b>{title}</b>' успешно создана! ID: {task.id}\nОписание: {description}", parse_mode='HTML')
    else:
        await message.answer("❌ Ошибка при создании задачи. Попробуйте позже.")
    
    await state.clear()

@dp.message(Command("list_tasks"))
async def cmd_list_tasks(message: Message):
    """Список задач пользователя."""
    telegram_id = message.from_user.id
    
    from dtimebot.services import task_service
    tasks = await task_service.get_user_tasks(telegram_id)
    
    if not tasks:
        await message.answer("📭 У вас пока нет задач. Создайте первую с помощью /create_task")
        return

    response_text = "📝 Ваши задачи:\n\n"
    for i, task_obj in enumerate(tasks, 1):
        response_text += (
            f"<b>{i}. {task_obj.title}</b>\n"
            f"   ID: {task_obj.id}\n"
            f"   Начало: {task_obj.time_start.strftime('%d.%m.%Y %H:%M') if task_obj.time_start else 'Не указано'}\n"
            f"   Окончание: {task_obj.time_end.strftime('%d.%m.%Y %H:%M') if task_obj.time_end else 'Не указано'}\n"
            f"   Описание: {task_obj.description or '-'}\n\n"
        )
    
    await message.answer(response_text, parse_mode='HTML')

@dp.message(Command("delete_task"))
async def cmd_delete_task_start(message: Message, state: FSMContext):
    """Начало удаления задачи: запрос ID."""
    telegram_id = message.from_user.id
    
    from dtimebot.services import task_service
    tasks = await task_service.get_user_tasks(telegram_id)
    
    if not tasks:
        await message.answer("📭 У вас нет задач для удаления.")
        return

    keyboard_buttons = []
    for task_obj in tasks:
        keyboard_buttons.append([f"{task_obj.id} - {task_obj.title}"])
    
    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    builder = ReplyKeyboardBuilder()
    for row in keyboard_buttons:
        builder.button(text=row[0])
    builder.button(text="❌ Отмена")
    builder.adjust(1) # Одна кнопка в ряду

    await message.answer(
        "Выберите задачу для удаления (отправьте её ID и название):",
        reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
    )
    await state.set_state(TaskStates.waiting_for_title) # Переиспользуем состояние для ID

@dp.message(TaskStates.waiting_for_title, F.text) # Используем то же состояние, что и для имени
async def cmd_delete_task_id_received(message: Message, state: FSMContext):
    """Получен ID задачи для удаления."""
    text = message.text.strip()
    
    if text.lower() == "❌ отмена":
        await message.answer("❌ Удаление отменено.", reply_markup=None)
        await state.clear()
        return

    try:
        # Пытаемся извлечь ID из текста "ID - Название"
        task_id_str = text.split(' - ')[0]
        task_id = int(task_id_str)
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат. Пожалуйста, выберите задачу из списка или отправьте ID.")
        return

    telegram_id = message.from_user.id
    
    from dtimebot.services import task_service
    success = await task_service.delete_task(telegram_id, task_id)
    
    if success:
        await message.answer(f"✅ Задача с ID {task_id} успешно удалена.", reply_markup=None)
    else:
        await message.answer("❌ Ошибка при удалении задачи. Возможно, она не существует или не принадлежит вам.", reply_markup=None)
    
    await state.clear()

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
