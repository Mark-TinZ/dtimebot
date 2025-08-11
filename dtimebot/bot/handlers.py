from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandObject
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
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

class JoinStates(StatesGroup):
    waiting_for_code = State()

# --- Команды общего назначения ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start - регистрация пользователя."""
    try:
        user = await user_service.get_or_create_user(message.from_user)
        if user is None:
            await message.answer("❌ Ошибка при регистрации пользователя.")
            return

        # Создаем личную директорию для пользователя, если её нет
        personal_dirs = await directory_service.get_user_directories(message.from_user.id)
        has_personal = any(dir_obj.is_self for dir_obj in personal_dirs)
        
        if not has_personal:
            await directory_service.create_directory(
                message.from_user.id, 
                "Личная", 
                "Личная директория пользователя",
                is_self=True
            )

        welcome_text = (
            f"👋 Привет, {message.from_user.first_name}!\n\n"
            "🤖 Я бот для управления задачами и событиями.\n"
            "📁 Создавайте директории, управляйте задачами и приглашайте друзей!\n\n"
            "📋 <b>Основные команды:</b>\n"
            "/help - Список всех команд\n"
            "/create_dir - Создать директорию\n"
            "/create_task - Создать задачу\n"
            "/directories - Ваши директории\n"
            "/list_tasks - Ваши задачи\n\n"
            "💡 Используйте /help для полного списка команд."
        )
        
        await message.answer(welcome_text, parse_mode='HTML')
        
    except Exception as e:
        logger.exception("Error in /start command: %s", e)
        await message.answer("❌ Произошла ошибка при запуске бота.")

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

    builder = InlineKeyboardBuilder()
    for dir_obj in directories:
        builder.button(text=f"{dir_obj.name} (ID: {dir_obj.id})", callback_data=f"edit_dir_select_{dir_obj.id}")
    builder.button(text="❌ Отмена", callback_data="edit_dir_cancel")
    builder.adjust(1)

    await message.answer(
        "Выберите директорию для редактирования:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("edit_dir_select_"))
async def cmd_edit_dir_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрана директория для редактирования."""
    directory_id = int(callback.data.split('_')[-1])
    
    # Сохраняем ID директории и показываем меню редактирования
    await state.update_data(directory_id=directory_id)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Изменить название", callback_data=f"edit_dir_name_{directory_id}")
    builder.button(text="📄 Изменить описание", callback_data=f"edit_dir_desc_{directory_id}")
    builder.button(text="🏷️ Управление тегами", callback_data=f"edit_dir_tags_{directory_id}")
    builder.adjust(1)
    
    await callback.message.answer(
        "Выберите, что хотите изменить:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "edit_dir_cancel")
async def cmd_edit_dir_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования директории."""
    await callback.message.answer("❌ Редактирование отменено.")
    await callback.answer()

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
    """Начало удаления директории: выбор директории."""
    telegram_id = message.from_user.id
    
    directories = await directory_service.get_user_directories(telegram_id)
    
    if not directories:
        await message.answer("📭 У вас нет директорий для удаления.")
        return

    builder = InlineKeyboardBuilder()
    for dir_obj in directories:
        if not dir_obj.is_self:  # Не показываем личные директории для удаления
            builder.button(text=f"{dir_obj.name} (ID: {dir_obj.id})", callback_data=f"delete_dir_select_{dir_obj.id}")
    builder.button(text="❌ Отмена", callback_data="delete_dir_cancel")
    builder.adjust(1)

    await message.answer(
        "Выберите директорию для удаления:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("delete_dir_select_"))
async def cmd_delete_dir_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрана директория для удаления."""
    directory_id = int(callback.data.split('_')[-1])
    telegram_id = callback.from_user.id
    
    success = await directory_service.delete_directory(telegram_id, directory_id)
    
    if success:
        await callback.message.answer(f"✅ Директория с ID {directory_id} успешно удалена.")
    else:
        await callback.message.answer("❌ Ошибка при удалении директории. Возможно, она не существует, не принадлежит вам или является личной директорией.")
    
    await callback.answer()

@router.callback_query(F.data == "delete_dir_cancel")
async def cmd_delete_dir_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления директории."""
    await callback.message.answer("❌ Удаление отменено.")
    await callback.answer()

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

    builder = InlineKeyboardBuilder()
    for task_obj in tasks:
        builder.button(text=f"{task_obj.title} (ID: {task_obj.id})", callback_data=f"edit_task_select_{task_obj.id}")
    builder.button(text="❌ Отмена", callback_data="edit_task_cancel")
    builder.adjust(1)

    await message.answer(
        "Выберите задачу для редактирования:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("edit_task_select_"))
async def cmd_edit_task_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрана задача для редактирования."""
    task_id = int(callback.data.split('_')[-1])
    
    # Сохраняем ID задачи и показываем меню редактирования
    await state.update_data(task_id=task_id)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Изменить название", callback_data=f"edit_task_title_{task_id}")
    builder.button(text="📄 Изменить описание", callback_data=f"edit_task_desc_{task_id}")
    builder.button(text="🏷️ Управление тегами", callback_data=f"edit_task_tags_{task_id}")
    builder.adjust(1)
    
    await callback.message.answer(
        "Выберите, что хотите изменить:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "edit_task_cancel")
async def cmd_edit_task_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования задачи."""
    await callback.message.answer("❌ Редактирование отменено.")
    await callback.answer()

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
    """Начало удаления задачи: выбор задачи."""
    telegram_id = message.from_user.id

    tasks = await task_service.get_user_tasks(telegram_id)

    if not tasks:
        await message.answer("📭 У вас нет задач для удаления.")
        return

    builder = InlineKeyboardBuilder()
    for task_obj in tasks:
        builder.button(text=f"{task_obj.title} (ID: {task_obj.id})", callback_data=f"delete_task_select_{task_obj.id}")
    builder.button(text="❌ Отмена", callback_data="delete_task_cancel")
    builder.adjust(1)

    await message.answer(
        "Выберите задачу для удаления:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("delete_task_select_"))
async def cmd_delete_task_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрана задача для удаления."""
    task_id = int(callback.data.split('_')[-1])
    telegram_id = callback.from_user.id
    
    success = await task_service.delete_task(telegram_id, task_id)
    
    if success:
        await callback.message.answer(f"✅ Задача с ID {task_id} успешно удалена.")
    else:
        await callback.message.answer("❌ Ошибка при удалении задачи. Возможно, она не существует или не принадлежит вам.")
    
    await callback.answer()

@router.callback_query(F.data == "delete_task_cancel")
async def cmd_delete_task_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления задачи."""
    await callback.message.answer("❌ Удаление отменено.")
    await callback.answer()

# --- Команды для работы с приглашениями ---

@router.message(Command("invite"))
async def cmd_invite_start(message: Message, state: FSMContext):
    """Начало создания приглашения: выбор директории."""
    telegram_id = message.from_user.id
    
    directories = await directory_service.get_user_directories(telegram_id)
    
    if not directories:
        await message.answer("📭 У вас нет директорий для создания приглашений.")
        return

    builder = InlineKeyboardBuilder()
    for dir_obj in directories:
        if not dir_obj.is_self:  # Не показываем личные директории для приглашений
            builder.button(text=f"{dir_obj.name} (ID: {dir_obj.id})", callback_data=f"invite_dir_select_{dir_obj.id}")
    builder.button(text="❌ Отмена", callback_data="invite_cancel")
    builder.adjust(1)

    await message.answer(
        "Выберите директорию для создания приглашения:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("invite_dir_select_"))
async def cmd_invite_directory_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрана директория для приглашения."""
    directory_id = int(callback.data.split('_')[-1])
    
    await state.update_data(directory_id=directory_id)
    await callback.message.answer(
        "Введите максимальное количество использований приглашения (или 0 для неограниченного):"
    )
    await state.set_state(InvitationStates.waiting_for_max_uses)
    await callback.answer()

@router.callback_query(F.data == "invite_cancel")
async def cmd_invite_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена создания приглашения."""
    await callback.message.answer("❌ Создание приглашения отменено.")
    await callback.answer()

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
    if command.args:
        # Если код передан как аргумент команды
        code = command.args.strip().upper()
        await process_join_code(message, code)
    else:
        # Если код не передан, запрашиваем его
        await message.answer("Введите код приглашения:")
        await message.bot.set_state(message.from_user.id, JoinStates.waiting_for_code)

async def process_join_code(message: Message, code: str):
    """Обработка кода приглашения."""
    telegram_id = message.from_user.id
    success = await invitation_service.join_directory_by_code(telegram_id, code)
    
    if success:
        await message.answer("✅ Вы успешно присоединились к директории!")
    else:
        await message.answer("❌ Не удалось присоединиться к директории. Возможно, код неверный или истек срок действия.")

@router.message(JoinStates.waiting_for_code, F.text)
async def cmd_join_code_received(message: Message, state: FSMContext):
    """Получен код приглашения."""
    code = message.text.strip().upper()
    await process_join_code(message, code)
    await state.clear()

@router.message(Command("members"))
async def cmd_list_members(message: Message, command: CommandObject):
    """Список участников директории."""
    telegram_id = message.from_user.id
    
    # Получаем все директории пользователя (где он владелец или участник)
    user_directories = await directory_service.get_user_directories(telegram_id)
    
    if not user_directories:
        await message.answer("📭 У вас нет директорий для просмотра участников.")
        return

    builder = InlineKeyboardBuilder()
    for dir_obj in user_directories:
        builder.button(text=f"{dir_obj.name} (ID: {dir_obj.id})", callback_data=f"members_dir_{dir_obj.id}")
    builder.button(text="❌ Отмена", callback_data="members_cancel")
    builder.adjust(1)

    await message.answer(
        "Выберите директорию для просмотра участников:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("members_dir_"))
async def cmd_members_directory_selected(callback: CallbackQuery):
    """Выбрана директория для просмотра участников."""
    directory_id = int(callback.data.split('_')[-1])
    telegram_id = callback.from_user.id
    
    members = await invitation_service.get_directory_members(telegram_id, directory_id)
    
    if members is None:
        await callback.message.answer("❌ Директория не найдена или у вас нет прав для просмотра участников.")
        await callback.answer()
        return

    if not members:
        await callback.message.answer("📭 В этой директории пока нет участников.")
        await callback.answer()
        return

    # Получаем информацию о директории
    directory = await directory_service.get_directory_by_id(telegram_id, directory_id)
    dir_name = directory.name if directory else f"Директория {directory_id}"
    
    response_text = f"👥 Участники директории '{dir_name}' (ID: {directory_id}):\n\n"
    for i, member in enumerate(members, 1):
        # Не показываем ID пользователей другим пользователям
        response_text += f"{i}. Пользователь\n"
    
    await callback.message.answer(response_text)
    await callback.answer()

@router.callback_query(F.data == "members_cancel")
async def cmd_members_cancel(callback: CallbackQuery):
    """Отмена просмотра участников."""
    await callback.message.answer("❌ Просмотр участников отменен.")
    await callback.answer()

@router.message(Command("leave"))
async def cmd_leave_directory(message: Message, command: CommandObject):
    """Покинуть директорию."""
    telegram_id = message.from_user.id
    
    # Получаем все директории пользователя (где он участник, но не владелец)
    user_directories = await directory_service.get_user_directories(telegram_id)
    
    if not user_directories:
        await message.answer("📭 У вас нет директорий для выхода.")
        return

    builder = InlineKeyboardBuilder()
    for dir_obj in user_directories:
        if not dir_obj.is_self:  # Не показываем личные директории для выхода
            builder.button(text=f"{dir_obj.name} (ID: {dir_obj.id})", callback_data=f"leave_dir_{dir_obj.id}")
    builder.button(text="❌ Отмена", callback_data="leave_cancel")
    builder.adjust(1)

    await message.answer(
        "Выберите директорию для выхода:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("leave_dir_"))
async def cmd_leave_directory_selected(callback: CallbackQuery):
    """Выбрана директория для выхода."""
    directory_id = int(callback.data.split('_')[-1])
    telegram_id = callback.from_user.id
    
    success = await invitation_service.leave_directory(telegram_id, directory_id)
    
    if success:
        await callback.message.answer(f"✅ Вы успешно покинули директорию {directory_id}.")
    else:
        await callback.message.answer("❌ Не удалось покинуть директорию. Возможно, вы не являетесь участником или являетесь владельцем.")
    
    await callback.answer()

@router.callback_query(F.data == "leave_cancel")
async def cmd_leave_cancel(callback: CallbackQuery):
    """Отмена выхода из директории."""
    await callback.message.answer("❌ Выход из директории отменен.")
    await callback.answer()

# --- Команды для работы с тегами ---

@router.message(Command("add_tag"))
async def cmd_add_tag_start(message: Message, state: FSMContext):
    """Добавление тега к директории или задаче."""
    telegram_id = message.from_user.id
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📁 Добавить к директории", callback_data="add_tag_dir")
    builder.button(text="📝 Добавить к задаче", callback_data="add_tag_task")
    builder.button(text="❌ Отмена", callback_data="add_tag_cancel")
    builder.adjust(1)

    await message.answer(
        "Выберите тип объекта для добавления тега:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "add_tag_dir")
async def cmd_add_tag_dir_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрано добавление тега к директории."""
    telegram_id = callback.from_user.id
    
    directories = await directory_service.get_user_directories(telegram_id)
    
    if not directories:
        await callback.message.answer("📭 У вас нет директорий для добавления тегов.")
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for dir_obj in directories:
        builder.button(text=f"{dir_obj.name} (ID: {dir_obj.id})", callback_data=f"add_tag_dir_select_{dir_obj.id}")
    builder.button(text="❌ Отмена", callback_data="add_tag_cancel")
    builder.adjust(1)

    await callback.message.answer(
        "Выберите директорию для добавления тега:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "add_tag_task")
async def cmd_add_tag_task_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрано добавление тега к задаче."""
    telegram_id = callback.from_user.id
    
    tasks = await task_service.get_user_tasks(telegram_id)
    
    if not tasks:
        await callback.message.answer("📭 У вас нет задач для добавления тегов.")
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for task_obj in tasks:
        builder.button(text=f"{task_obj.title} (ID: {task_obj.id})", callback_data=f"add_tag_task_select_{task_obj.id}")
    builder.button(text="❌ Отмена", callback_data="add_tag_cancel")
    builder.adjust(1)

    await callback.message.answer(
        "Выберите задачу для добавления тега:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(F.data.startswith("add_tag_dir_select_"))
async def cmd_add_tag_dir_object_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрана директория для добавления тега."""
    directory_id = int(callback.data.split('_')[-1])
    await state.update_data(obj_type='dir', obj_id=directory_id)
    await callback.message.answer("Введите тег для добавления:")
    await state.set_state(DirectoryStates.waiting_for_tag)
    await callback.answer()

@router.callback_query(F.data.startswith("add_tag_task_select_"))
async def cmd_add_tag_task_object_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрана задача для добавления тега."""
    task_id = int(callback.data.split('_')[-1])
    await state.update_data(obj_type='task', obj_id=task_id)
    await callback.message.answer("Введите тег для добавления:")
    await state.set_state(TaskStates.waiting_for_tag)
    await callback.answer()

@router.callback_query(F.data == "add_tag_cancel")
async def cmd_add_tag_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления тега."""
    await callback.message.answer("❌ Добавление тега отменено.")
    await callback.answer()

@router.message(DirectoryStates.waiting_for_tag, F.text)
async def cmd_add_tag_value_received(message: Message, state: FSMContext):
    """Получен тег для добавления к директории."""
    user_data = await state.get_data()
    directory_id = user_data['obj_id']
    tag = message.text.strip()
    telegram_id = message.from_user.id

    success = await directory_service.add_tag_to_directory(telegram_id, directory_id, tag)
    
    if success:
        await message.answer(f"✅ Тег '{tag}' добавлен к директории {directory_id}.")
    else:
        await message.answer(f"❌ Не удалось добавить тег к директории {directory_id}.")
    
    await state.clear()

@router.message(TaskStates.waiting_for_tag, F.text)
async def cmd_add_tag_task_value_received(message: Message, state: FSMContext):
    """Получен тег для добавления к задаче."""
    user_data = await state.get_data()
    task_id = user_data['obj_id']
    tag = message.text.strip()
    telegram_id = message.from_user.id

    success = await task_service.add_tag_to_task(telegram_id, task_id, tag)
    
    if success:
        await message.answer(f"✅ Тег '{tag}' добавлен к задаче {task_id}.")
    else:
        await message.answer(f"❌ Не удалось добавить тег к задаче {task_id}.")
    
    await state.clear()

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

@router.message(Command("my_invitations"))
async def cmd_my_invitations(message: Message):
    """Показать директории, куда приглашен пользователь."""
    telegram_id = message.from_user.id
    
    # Получаем все директории пользователя
    user_directories = await directory_service.get_user_directories(telegram_id)
    
    if not user_directories:
        await message.answer("📭 У вас нет директорий.")
        return

    # Разделяем на владельца и участника
    owned_dirs = []
    member_dirs = []
    
    for dir_obj in user_directories:
        if dir_obj.is_self:
            continue  # Пропускаем личные директории
        elif dir_obj.owner_id == telegram_id:
            owned_dirs.append(dir_obj)
        else:
            member_dirs.append(dir_obj)

    response_text = "📁 <b>Ваши директории:</b>\n\n"
    
    if owned_dirs:
        response_text += "👑 <b>Директории, которыми вы владеете:</b>\n"
        for dir_obj in owned_dirs:
            response_text += f"• {dir_obj.name} (ID: {dir_obj.id})\n"
        response_text += "\n"
    
    if member_dirs:
        response_text += "👥 <b>Директории, в которые вы приглашены:</b>\n"
        for dir_obj in member_dirs:
            response_text += f"• {dir_obj.name} (ID: {dir_obj.id})\n"
    else:
        response_text += "👥 <b>Директории, в которые вы приглашены:</b>\n"
        response_text += "Пока нет приглашений в другие директории.\n"
    
    await message.answer(response_text, parse_mode='HTML')

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
        "/add_tag - Добавить тег (интерактивно)\n"
        "/remove_tag [dir/task] [ID] [тег] - Удалить тег\n\n"
        "👥 <b>Команды для приглашений:</b>\n"
        "/invite - Создать приглашение\n"
        "/join [код] - Присоединиться по коду\n"
        "/members - Список участников (интерактивно)\n"
        "/leave - Покинуть директорию (интерактивно)\n"
        "/my_invitations - Мои директории и приглашения\n\n"
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
