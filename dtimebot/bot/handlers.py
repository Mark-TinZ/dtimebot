from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from sqlalchemy import select
from dtimebot.database import get_session

from dtimebot.logs import main_logger
from dtimebot.models.users import User
from dtimebot.services import user_service, directory_service, task_service, invitation_service

logger = main_logger.getChild('bot.handlers')

router = Router()

# --- Определение состояний для FSM ---
class DirectoryStates(StatesGroup):
	waiting_for_name = State()
	waiting_for_description = State()
	waiting_for_edit_field = State()
	waiting_for_edit_value = State()
	waiting_for_tag = State()
	waiting_for_tag_action = State()  # add/remove

class TaskStates(StatesGroup):
	waiting_for_title = State()
	waiting_for_description = State()
	waiting_for_edit_field = State()
	waiting_for_edit_value = State()
	waiting_for_tag = State()
	waiting_for_tag_action = State()  # add/remove

class InvitationStates(StatesGroup):
	waiting_for_directory = State()
	waiting_for_max_uses = State()
	waiting_for_expiry_days = State()

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

@router.message(Command("edit_dir"))
async def cmd_edit_dir_start(message: Message, state: FSMContext):
	"""Начало редактирования директории: выбор директории."""
	telegram_id = message.from_user.id
	
	directories = await directory_service.get_user_directories(telegram_id)
	
	if not directories:
		await message.answer("📭 У вас нет директорий для редактирования.")
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
		"Выберите директорию для редактирования:",
		reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
	)
	await state.set_state(DirectoryStates.waiting_for_name)

@router.message(DirectoryStates.waiting_for_name, F.text)
async def cmd_edit_dir_selected(message: Message, state: FSMContext):
	"""Выбрана директория для редактирования."""
	text = message.text.strip()
	
	if text.lower() == "❌ отмена":
		await message.answer("❌ Редактирование отменено.", reply_markup=None)
		await state.clear()
		return

	try:
		dir_id_str = text.split(' - ')[0]
		directory_id = int(dir_id_str)
	except (ValueError, IndexError):
		await message.answer("❌ Неверный формат. Пожалуйста, выберите директорию из списка.")
		return

	# Сохраняем ID директории и показываем меню редактирования
	await state.update_data(directory_id=directory_id)
	
	builder = InlineKeyboardBuilder()
	builder.button(text="📝 Изменить название", callback_data=f"edit_dir_name_{directory_id}")
	builder.button(text="📄 Изменить описание", callback_data=f"edit_dir_desc_{directory_id}")
	builder.button(text="🏷️ Управление тегами", callback_data=f"edit_dir_tags_{directory_id}")
	builder.adjust(1)
	
	await message.answer(
		"Выберите, что хотите изменить:",
		reply_markup=builder.as_markup(),
		reply_to_message_id=message.message_id
	)

@router.callback_query(F.data.startswith("edit_dir_name_"))
async def edit_directory_name_callback(callback: CallbackQuery, state: FSMContext):
	"""Обработчик кнопки изменения названия директории."""
	directory_id = int(callback.data.split('_')[-1])
	await state.update_data(directory_id=directory_id, edit_field='name')
	await callback.message.answer("Введите новое название директории:")
	await state.set_state(DirectoryStates.waiting_for_edit_value)
	await callback.answer()

@router.callback_query(F.data.startswith("edit_dir_desc_"))
async def edit_directory_description_callback(callback: CallbackQuery, state: FSMContext):
	"""Обработчик кнопки изменения описания директории."""
	directory_id = int(callback.data.split('_')[-1])
	await state.update_data(directory_id=directory_id, edit_field='description')
	await callback.message.answer("Введите новое описание директории:")
	await state.set_state(DirectoryStates.waiting_for_edit_value)
	await callback.answer()

@router.callback_query(F.data.startswith("edit_dir_tags_"))
async def edit_directory_tags_callback(callback: CallbackQuery, state: FSMContext):
	"""Обработчик кнопки управления тегами директории."""
	directory_id = int(callback.data.split('_')[-1])
	await state.update_data(directory_id=directory_id)
	
	builder = InlineKeyboardBuilder()
	builder.button(text="➕ Добавить тег", callback_data=f"add_dir_tag_{directory_id}")
	builder.button(text="➖ Удалить тег", callback_data=f"remove_dir_tag_{directory_id}")
	builder.button(text="📋 Показать теги", callback_data=f"show_dir_tags_{directory_id}")
	builder.adjust(1)
	
	await callback.message.answer(
		"Выберите действие с тегами:",
		reply_markup=builder.as_markup()
	)
	await callback.answer()

@router.message(DirectoryStates.waiting_for_edit_value, F.text)
async def cmd_edit_dir_value_received(message: Message, state: FSMContext):
	"""Получено новое значение для редактирования директории."""
	user_data = await state.get_data()
	directory_id = user_data['directory_id']
	edit_field = user_data['edit_field']
	new_value = message.text
	telegram_id = message.from_user.id

	success = False
	if edit_field == 'name':
		success = await directory_service.update_directory(telegram_id, directory_id, name=new_value)
	elif edit_field == 'description':
		success = await directory_service.update_directory(telegram_id, directory_id, description=new_value)

	if success:
		await message.answer(f"✅ {edit_field.capitalize()} директории успешно обновлено!")
	else:
		await message.answer("❌ Ошибка при обновлении директории.")
	
	await state.clear()

@router.message(Command("delete_dir"))
async def cmd_delete_dir_start(message: Message, state: FSMContext):
	"""Начало удаления директории: запрос ID."""
	telegram_id = message.from_user.id
	
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
		dir_id_str = text.split(' - ')[0]
		directory_id = int(dir_id_str)
	except (ValueError, IndexError):
		await message.answer("❌ Неверный формат. Пожалуйста, выберите директорию из списка.")
		return

	telegram_id = message.from_user.id
	success = await directory_service.delete_directory(telegram_id, directory_id)
	
	if success:
		await message.answer(f"✅ Директория с ID {directory_id} успешно удалена.", reply_markup=None)
	else:
		await message.answer("❌ Ошибка при удалении директории. Возможно, она не существует, не принадлежит вам или является личной директорией.", reply_markup=None)
	
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

@router.message(Command("edit_task"))
async def cmd_edit_task_start(message: Message, state: FSMContext):
	"""Начало редактирования задачи: выбор задачи."""
	telegram_id = message.from_user.id
	
	tasks = await task_service.get_user_tasks(telegram_id)
	
	if not tasks:
		await message.answer("📭 У вас нет задач для редактирования.")
		return

	keyboard_buttons = []
	for task_obj in tasks:
		keyboard_buttons.append([f"{task_obj.id} - {task_obj.title}"])
	
	builder = ReplyKeyboardBuilder()
	for row in keyboard_buttons:
		builder.button(text=row[0])
	builder.button(text="❌ Отмена")
	builder.adjust(1)

	await message.answer(
		"Выберите задачу для редактирования:",
		reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
	)
	await state.set_state(TaskStates.waiting_for_title)

@router.message(TaskStates.waiting_for_title, F.text)
async def cmd_edit_task_selected(message: Message, state: FSMContext):
	"""Выбрана задача для редактирования."""
	text = message.text.strip()
	
	if text.lower() == "❌ отмена":
		await message.answer("❌ Редактирование отменено.", reply_markup=None)
		await state.clear()
		return

	try:
		task_id_str = text.split(' - ')[0]
		task_id = int(task_id_str)
	except (ValueError, IndexError):
		await message.answer("❌ Неверный формат. Пожалуйста, выберите задачу из списка.")
		return

	# Сохраняем ID задачи и показываем меню редактирования
	await state.update_data(task_id=task_id)
	
	builder = InlineKeyboardBuilder()
	builder.button(text="📝 Изменить название", callback_data=f"edit_task_title_{task_id}")
	builder.button(text="📄 Изменить описание", callback_data=f"edit_task_desc_{task_id}")
	builder.button(text="🏷️ Управление тегами", callback_data=f"edit_task_tags_{task_id}")
	builder.adjust(1)
	
	await message.answer(
		"Выберите, что хотите изменить:",
		reply_markup=builder.as_markup(),
		reply_to_message_id=message.message_id
	)

@router.callback_query(F.data.startswith("edit_task_title_"))
async def edit_task_title_callback(callback: CallbackQuery, state: FSMContext):
	"""Обработчик кнопки изменения названия задачи."""
	task_id = int(callback.data.split('_')[-1])
	await state.update_data(task_id=task_id, edit_field='title')
	await callback.message.answer("Введите новое название задачи:")
	await state.set_state(TaskStates.waiting_for_edit_value)
	await callback.answer()

@router.callback_query(F.data.startswith("edit_task_desc_"))
async def edit_task_description_callback(callback: CallbackQuery, state: FSMContext):
	"""Обработчик кнопки изменения описания задачи."""
	task_id = int(callback.data.split('_')[-1])
	await state.update_data(task_id=task_id, edit_field='description')
	await callback.message.answer("Введите новое описание задачи:")
	await state.set_state(TaskStates.waiting_for_edit_value)
	await callback.answer()

@router.callback_query(F.data.startswith("edit_task_tags_"))
async def edit_task_tags_callback(callback: CallbackQuery, state: FSMContext):
	"""Обработчик кнопки управления тегами задачи."""
	task_id = int(callback.data.split('_')[-1])
	await state.update_data(task_id=task_id)
	
	builder = InlineKeyboardBuilder()
	builder.button(text="➕ Добавить тег", callback_data=f"add_task_tag_{task_id}")
	builder.button(text="➖ Удалить тег", callback_data=f"remove_task_tag_{task_id}")
	builder.button(text="📋 Показать теги", callback_data=f"show_task_tags_{task_id}")
	builder.adjust(1)
	
	await callback.message.answer(
		"Выберите действие с тегами:",
		reply_markup=builder.as_markup()
	)
	await callback.answer()

@router.message(TaskStates.waiting_for_edit_value, F.text)
async def cmd_edit_task_value_received(message: Message, state: FSMContext):
	"""Получено новое значение для редактирования задачи."""
	user_data = await state.get_data()
	task_id = user_data['task_id']
	edit_field = user_data['edit_field']
	new_value = message.text
	telegram_id = message.from_user.id

	success = False
	if edit_field == 'title':
		success = await task_service.update_task(telegram_id, task_id, title=new_value)
	elif edit_field == 'description':
		success = await task_service.update_task(telegram_id, task_id, description=new_value)

	if success:
		await message.answer(f"✅ {edit_field.capitalize()} задачи успешно обновлено!")
	else:
		await message.answer("❌ Ошибка при обновлении задачи.")
	
	await state.clear()

@router.message(Command("delete_task"))
async def cmd_delete_task_start(message: Message, state: FSMContext):
	"""Начало удаления задачи: запрос ID."""
	telegram_id = message.from_user.id

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
		builder.adjust(1)

		await message.answer(
			"Выберите задачу для удаления (отправьте её ID и название):",
			reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
		)
		await state.set_state(TaskStates.waiting_for_title)

@router.message(TaskStates.waiting_for_title, F.text)
async def cmd_delete_task_id_received(message: Message, state: FSMContext):
	"""Получен ID задачи для удаления."""
	text = message.text.strip()
	
	if text.lower() == "❌ отмена":
		await message.answer("❌ Удаление отменено.", reply_markup=None)
		await state.clear()
		return

	try:
		task_id_str = text.split(' - ')[0]
		task_id = int(task_id_str)
	except (ValueError, IndexError):
		await message.answer("❌ Неверный формат. Пожалуйста, выберите задачу из списка.")
		return

	telegram_id = message.from_user.id
	success = await task_service.delete_task(telegram_id, task_id)
	
	if success:
		await message.answer(f"✅ Задача с ID {task_id} успешно удалена.", reply_markup=None)
	else:
		await message.answer("❌ Ошибка при удалении задачи. Возможно, она не существует или не принадлежит вам.", reply_markup=None)
	
	await state.clear()

# --- Команды для работы с приглашениями ---

@router.message(Command("invite"))
async def cmd_invite_start(message: Message, state: FSMContext):
	"""Начало создания приглашения: выбор директории."""
	telegram_id = message.from_user.id
	
	directories = await directory_service.get_user_directories(telegram_id)
	
	if not directories:
		await message.answer("📭 У вас нет директорий для создания приглашений.")
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
		"Выберите директорию для создания приглашения:",
		reply_markup=builder.as_markup(resize_keyboard=True, one_time_keyboard=True)
	)
	await state.set_state(InvitationStates.waiting_for_directory)

@router.message(InvitationStates.waiting_for_directory, F.text)
async def cmd_invite_directory_selected(message: Message, state: FSMContext):
	"""Выбрана директория для приглашения."""
	text = message.text.strip()
	
	if text.lower() == "❌ отмена":
		await message.answer("❌ Создание приглашения отменено.", reply_markup=None)
		await state.clear()
		return

	try:
		dir_id_str = text.split(' - ')[0]
		directory_id = int(dir_id_str)
	except (ValueError, IndexError):
		await message.answer("❌ Неверный формат. Пожалуйста, выберите директорию из списка.")
		return

	await state.update_data(directory_id=directory_id)
	await message.answer(
		"Введите максимальное количество использований приглашения (или 0 для неограниченного):",
		reply_markup=None
	)
	await state.set_state(InvitationStates.waiting_for_max_uses)

@router.message(InvitationStates.waiting_for_max_uses, F.text)
async def cmd_invite_max_uses_received(message: Message, state: FSMContext):
	"""Получено максимальное количество использований."""
	try:
		max_uses = int(message.text)
		if max_uses < 0:
			raise ValueError("Отрицательное число")
	except ValueError:
		await message.answer("❌ Пожалуйста, введите корректное число (0 или больше).")
		return

	await state.update_data(max_uses=max_uses if max_uses > 0 else None)
	await message.answer("Введите количество дней действия приглашения (или 0 для бессрочного):")
	await state.set_state(InvitationStates.waiting_for_expiry_days)

@router.message(InvitationStates.waiting_for_expiry_days, F.text)
async def cmd_invite_expiry_received(message: Message, state: FSMContext):
	"""Получено количество дней действия приглашения."""
	try:
		days = int(message.text)
		if days < 0:
			raise ValueError("Отрицательное число")
	except ValueError:
		await message.answer("❌ Пожалуйста, введите корректное число (0 или больше).")
		return

	user_data = await state.get_data()
	directory_id = user_data['directory_id']
	max_uses = user_data['max_uses']
	telegram_id = message.from_user.id

	# Вычисляем дату истечения
	from datetime import datetime, timedelta
	valid_until = None
	if days > 0:
		valid_until = datetime.utcnow() + timedelta(days=days)

	# Создаем приглашение
	invitation = await invitation_service.create_invitation(
		telegram_id, directory_id, max_uses, valid_until
	)

	if invitation:
		expiry_text = f"до {valid_until.strftime('%d.%m.%Y %H:%M')}" if valid_until else "бессрочно"
		uses_text = f"максимум {max_uses} использований" if max_uses else "неограниченно"
		
		await message.answer(
			f"✅ Приглашение создано!\n\n"
			f"🔑 Код: <code>{invitation.code}</code>\n"
			f"⏰ Действует: {expiry_text}\n"
			f"📊 Использований: {uses_text}\n\n"
			f"Отправьте этот код другому пользователю для присоединения к директории.",
			parse_mode='HTML'
		)
	else:
		await message.answer("❌ Ошибка при создании приглашения.")
	
	await state.clear()

@router.message(Command("join"))
async def cmd_join_directory(message: Message, command: CommandObject):
	"""Присоединение к директории по коду приглашения."""
	if not command.args:
		await message.answer("❌ Пожалуйста, укажите код приглашения.\nПример: /join ABC12345")
		return

	code = command.args.strip().upper()
	telegram_id = message.from_user.id

	success = await invitation_service.join_directory_by_code(telegram_id, code)
	
	if success:
		await message.answer("✅ Вы успешно присоединились к директории!")
	else:
		await message.answer("❌ Не удалось присоединиться к директории. Возможно, код неверный или истек срок действия.")

@router.message(Command("members"))
async def cmd_list_members(message: Message, command: CommandObject):
	"""Список участников директории."""
	if not command.args:
		await message.answer("❌ Пожалуйста, укажите ID директории.\nПример: /members 123")
		return

	try:
		directory_id = int(command.args.strip())
	except ValueError:
		await message.answer("❌ ID директории должен быть числом.")
		return

	telegram_id = message.from_user.id
	members = await invitation_service.get_directory_members(telegram_id, directory_id)
	
	if members is None:
		await message.answer("❌ Директория не найдена или у вас нет прав для просмотра участников.")
		return

	if not members:
		await message.answer("📭 В этой директории пока нет участников.")
		return

	response_text = f"👥 Участники директории (ID: {directory_id}):\n\n"
	for i, member in enumerate(members, 1):
		response_text += f"{i}. Пользователь ID: {member.telegram_id}\n"
	
	await message.answer(response_text)

@router.message(Command("leave"))
async def cmd_leave_directory(message: Message, command: CommandObject):
	"""Покинуть директорию."""
	if not command.args:
		await message.answer("❌ Пожалуйста, укажите ID директории.\nПример: /leave 123")
		return

	try:
		directory_id = int(command.args.strip())
	except ValueError:
		await message.answer("❌ ID директории должен быть числом.")
		return

	telegram_id = message.from_user.id
	success = await invitation_service.leave_directory(telegram_id, directory_id)
	
	if success:
		await message.answer(f"✅ Вы успешно покинули директорию {directory_id}.")
	else:
		await message.answer("❌ Не удалось покинуть директорию. Возможно, вы не являетесь участником или являетесь владельцем.")

# --- Команды для работы с тегами ---

@router.message(Command("add_tag"))
async def cmd_add_tag_start(message: Message, command: CommandObject):
	"""Добавление тега к директории или задаче."""
	if not command.args:
		await message.answer("❌ Пожалуйста, укажите тип объекта, ID и тег.\nПример: /add_tag dir 123 важное")
		return

	args = command.args.strip().split()
	if len(args) < 3:
		await message.answer("❌ Недостаточно аргументов.\nПример: /add_tag dir 123 важное")
		return

	obj_type = args[0].lower()
	try:
		obj_id = int(args[1])
	except ValueError:
		await message.answer("❌ ID должен быть числом.")
		return

	tag = ' '.join(args[2:])
	telegram_id = message.from_user.id

	success = False
	if obj_type == 'dir':
		success = await directory_service.add_tag_to_directory(telegram_id, obj_id, tag)
	elif obj_type == 'task':
		success = await task_service.add_tag_to_task(telegram_id, obj_id, tag)
	else:
		await message.answer("❌ Неверный тип объекта. Используйте 'dir' или 'task'.")
		return

	if success:
		await message.answer(f"✅ Тег '{tag}' добавлен к {obj_type} {obj_id}.")
	else:
		await message.answer(f"❌ Не удалось добавить тег к {obj_type} {obj_id}.")

@router.message(Command("remove_tag"))
async def cmd_remove_tag_start(message: Message, command: CommandObject):
	"""Удаление тега из директории или задачи."""
	if not command.args:
		await message.answer("❌ Пожалуйста, укажите тип объекта, ID и тег.\nПример: /remove_tag dir 123 важное")
		return

	args = command.args.strip().split()
	if len(args) < 3:
		await message.answer("❌ Недостаточно аргументов.\nПример: /remove_tag dir 123 важное")
		return

	obj_type = args[0].lower()
	try:
		obj_id = int(args[1])
	except ValueError:
		await message.answer("❌ ID должен быть числом.")
		return

	tag = ' '.join(args[2:])
	telegram_id = message.from_user.id

	success = False
	if obj_type == 'dir':
		success = await directory_service.remove_tag_from_directory(telegram_id, obj_id, tag)
	elif obj_type == 'task':
		success = await task_service.remove_tag_from_task(telegram_id, obj_id, tag)
	else:
		await message.answer("❌ Неверный тип объекта. Используйте 'dir' или 'task'.")
		return

	if success:
		await message.answer(f"✅ Тег '{tag}' удален из {obj_type} {obj_id}.")
	else:
		await message.answer(f"❌ Не удалось удалить тег из {obj_type} {obj_id}.")

# --- Команды общего назначения ---

@router.message(Command("help"))
async def on_help(message: Message):
	"""Обработчик команды /help."""
	help_text = (
		"🤖 Я бот для управления задачами и событиями!\n\n"
		"📁 <b>Команды для директорий:</b>\n"
		"/create_dir - Создать директорию\n"
		"/list_dirs - Список директорий\n"
		"/edit_dir - Редактировать директорию\n"
		"/delete_dir - Удалить директорию\n\n"
		"📝 <b>Команды для задач:</b>\n"
		"/create_task - Создать задачу\n"
		"/list_tasks - Список задач\n"
		"/edit_task - Редактировать задачу\n"
		"/delete_task - Удалить задачу\n\n"
		"🏷️ <b>Команды для тегов:</b>\n"
		"/add_tag [dir/task] [ID] [тег] - Добавить тег\n"
		"/remove_tag [dir/task] [ID] [тег] - Удалить тег\n\n"
		"👥 <b>Команды для приглашений:</b>\n"
		"/invite - Создать приглашение\n"
		"/join [код] - Присоединиться по коду\n"
		"/members [ID] - Список участников\n"
		"/leave [ID] - Покинуть директорию\n\n"
		"ℹ️ <b>Общие команды:</b>\n"
		"/start - Зарегистрироваться\n"
		"/me - Информация о вас\n"
		"/help - Это сообщение"
	)
	await message.answer(help_text, parse_mode='HTML')

@router.message(Command('me'))
async def on_me(message: Message):
	try:
		user = await user_service.get_or_create_user(message.from_user)
		if user is None:
			await message.answer("Не удалось получить информацию о пользователе.")
			return

		dirs = await directory_service.get_user_directories(message.from_user.id)
		tasks = await task_service.get_user_tasks(message.from_user.id)
		
		text = (
			f"👤 <b>Информация о пользователе:</b>\n\n"
			f"Имя: {message.from_user.full_name}\n"
			f"Username: @{message.from_user.username or 'Не указан'}\n"
			f"ID в системе: {user.id}\n"
			f"Telegram ID: {message.from_user.id}\n"
			f"Дата регистрации: {user.created_at.strftime('%d.%m.%Y %H:%M:%S') if user.created_at else 'Неизвестно'}\n\n"
			f"📊 <b>Статистика:</b>\n"
			f"Директорий: {len(dirs)}\n"
			f"Задач: {len(tasks)}"
		)
		await message.answer(text, parse_mode='HTML')
	except Exception as e:
		logger.exception("Error while retrieving user information for Telegram ID %s: %s", message.from_user.id, e)
		await message.answer("Произошла ошибка при выполнении /me.")
