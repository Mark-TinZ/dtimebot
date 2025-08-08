from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from sqlalchemy import select
from dtimebot.database import LocalSession

from dtimebot.logs import main_logger
from dtimebot.models.users import User
from dtimebot.services import user_service, directory_service, task_service


logger = main_logger.getChild('bot.handlers')

router = Router() # Создаем роутер для обработчиков

# --- Определение состояний для FSM ---
class DirectoryStates(StatesGroup):
	waiting_for_name = State()
	waiting_for_description = State()
	waiting_for_tag = State() # Для добавления/удаления тегов

class TaskStates(StatesGroup):
	waiting_for_title = State()
	waiting_for_description = State()
	waiting_for_tag = State() # Для добавления/удаления тегов

# --- Команды для работы с директориями ---

@router.message(Command("create_dir"))
async def cmd_create_dir_start(message: Message, state: FSMContext):
	"""Начало создания директории: запрос названия."""
	await message.answer("Введите название новой директории:")
	await state.set_state(DirectoryStates.waiting_for_name)

@router.message(DirectoryStates.waiting_for_name, F.text)
async def cmd_create_dir_name_received(message: Message, state: FSMContext):
	"""Получено название директории, запрос описания."""
	await state.update_data(name=message.text)
	await message.answer("Введите описание директории (или отправьте /skip, чтобы пропустить):")
	await state.set_state(DirectoryStates.waiting_for_description)

@router.message(DirectoryStates.waiting_for_description, Command("skip"))
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

@router.message(DirectoryStates.waiting_for_description, F.text)
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

@router.message(Command("directories"))
@router.message(Command("list_dirs"))
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
		# Получим теги для отображения
		tags = await directory_service.get_directory_tags(telegram_id, dir_obj.id)
		tags_str = ', '.join(tags) if tags else '-'
		response_text += (
			f"<b>{i}. {dir_obj.name}</b>\n"
			f"   ID: {dir_obj.id}\n"
			f"   Создана: {dir_obj.created_at.strftime('%d.%m.%Y %H:%M') if dir_obj.created_at else 'Неизвестно'}\n"
			f"   Описание: {dir_obj.description or '-'}\n"
			f"   Теги: {tags_str}\n\n"
		)
	
	await message.answer(response_text, parse_mode='HTML')

@router.message(Command("delete_dir"))
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
	
	builder = ReplyKeyboardBuilder()
	for row in keyboard_buttons:
		builder.button(text=row[0])
	builder.button(text="❌ Отмена")
	builder.adjust(1)

	await message.answer(
		"Выберите директорию для удаления (отправьте её ID и название):",
		reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
	)
	await state.set_state(DirectoryStates.waiting_for_name)

@router.message(DirectoryStates.waiting_for_name, F.text)
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

@router.message(Command("create_task"))
async def cmd_create_task_start(message: Message, state: FSMContext):
	"""Начало создания задачи: запрос названия."""
	await message.answer("Введите название новой задачи:")
	await state.set_state(TaskStates.waiting_for_title)

@router.message(TaskStates.waiting_for_title, F.text)
async def cmd_create_task_title_received(message: Message, state: FSMContext):
	"""Получено название задачи, запрос описания."""
	await state.update_data(title=message.text)
	await message.answer("Введите описание задачи (или отправьте /skip, чтобы пропустить):")
	await state.set_state(TaskStates.waiting_for_description)

@router.message(TaskStates.waiting_for_description, Command("skip"))
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

@router.message(TaskStates.waiting_for_description, F.text)
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

@router.message(Command("list_tasks"))
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
		# Получим теги для отображения
		tags = await task_service.get_task_tags(telegram_id, task_obj.id)
		tags_str = ', '.join(tags) if tags else '-'
		response_text += (
			f"<b>{i}. {task_obj.title}</b>\n"
			f"   ID: {task_obj.id}\n"
			f"   Начало: {task_obj.time_start.strftime('%d.%m.%Y %H:%M') if task_obj.time_start else 'Не указано'}\n"
			f"   Окончание: {task_obj.time_end.strftime('%d.%m.%Y %H:%M') if task_obj.time_end else 'Не указано'}\n"
			f"   Описание: {task_obj.description or '-'}\n"
			f"   Теги: {tags_str}\n\n"
		)
	
	await message.answer(response_text, parse_mode='HTML')

@router.message(Command("delete_task"))
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

@router.message(TaskStates.waiting_for_title, F.text) # Используем то же состояние, что и для имени
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


# ... (остальные обработчики команд для директорий и задач)

# --- Команды общего назначения ---
@router.message(Command("help"))
async def on_help(message: Message):
	"""Обработчик команды /help."""
	help_text = (
		"Я бот для управления задачами и событиями!\n"
		"Доступные команды:\n"
		"/start - Зарегистрироваться/начать работу\n"
		"/help - Показать это сообщение\n"
		"/me - Показать информацию о вас\n"
		"/create_dir - Создать директорию\n"
		"/list_dirs - Список директорий\n"
		"/delete_dir - Удалить директорию\n"
		"/create_task - Создать задачу\n"
		"/list_tasks - Список задач\n"
		"/delete_task - Удалить задачу\n"
	)
	await message.answer(help_text)

@router.message(Command('me'))
async def on_me(message: Message):
    try:
        # В user_service реализована логика get_or_create_user
        user = await user_service.get_or_create_user(message.from_user)
        if user is None:
            await message.answer("Не удалось получить информацию о пользователе.")
            return

        # Получаем директории пользователя
        dirs = await directory_service.get_user_directories(message.from_user.id)
        text = f"Пользователь: {message.from_user.full_name}\nID в системе: {user.id}\nДиректорий: {len(dirs)}"
        await message.answer(text)
    except Exception as e:
        logger.exception("Error while retrieving user information for Telegram ID %s: %s", message.from_user.id, e)
        await message.answer("Произошла ошибка при выполнении /me.")
