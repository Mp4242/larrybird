from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.utils import get_user, update_user
from datetime import date

settings_router = Router()

class SettingsState(StatesGroup):
    pseudo = State()
    emoji = State()
    quit_date = State()
    period = State()  # Pas besoin notifs state, toggle direct

@settings_router.message(Command("settings"))
async def settings_handler(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.reply("Профиль не найден. Сначала /start!")
        return
    notifs_status = 'Вкл' if user.notifications_enabled else 'Выкл'
    text = f"Текущие настройки:\n- Псевдоним: {user.pseudo}\n- Эмодзи: {user.avatar_emoji}\n- Дата отказа: {user.quit_date or 'Не указана'}\n- Уведомления: {notifs_status}\n- Период: {user.notification_period} дней"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить псевдоним", callback_data="edit_pseudo")],
        [InlineKeyboardButton(text="Изменить эмодзи", callback_data="edit_emoji")],
        [InlineKeyboardButton(text="Изменить дату отказа", callback_data="edit_quit_date")],
        [InlineKeyboardButton(text="Уведомления Вкл/Выкл", callback_data="toggle_notifs")],
        [InlineKeyboardButton(text="Изменить период уведомлений", callback_data="edit_period")]
    ])
    await message.answer(text, reply_markup=keyboard)

@settings_router.callback_query(F.data == "edit_pseudo")
async def edit_pseudo(query: CallbackQuery, state: FSMContext):
    await query.message.reply("Новый псевдоним (1-30 символов):")
    await state.set_state(SettingsState.pseudo)

@settings_router.message(SettingsState.pseudo)
async def save_pseudo(message: Message, state: FSMContext):
    pseudo = message.text.strip()
    if not 1 <= len(pseudo) <= 30:
        await message.reply("Неверно! Попробуйте снова.")
        return
    await update_user(message.from_user.id, pseudo=pseudo)
    await message.reply("Псевдоним обновлён! 🎉")
    await state.clear()

@settings_router.callback_query(F.data == "edit_emoji")
async def edit_emoji(query: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤", callback_data="set_emoji_👤")],
        [InlineKeyboardButton(text="🐶", callback_data="set_emoji_🐶"), InlineKeyboardButton(text="😎", callback_data="set_emoji_😎")],
        # Добавьте больше опций
    ])
    await query.message.edit_text("Выберите эмодзи:", reply_markup=keyboard)

@settings_router.callback_query(F.data.startswith("set_emoji_"))
async def save_emoji(query: CallbackQuery, state: FSMContext):
    emoji = query.data.split("_")[2]
    await update_user(query.from_user.id, avatar_emoji=emoji)
    await query.message.edit_text("Эмодзи обновлён! 🎉")
    await state.clear()

@settings_router.callback_query(F.data == "edit_quit_date")
async def edit_quit_date(query: CallbackQuery, state: FSMContext):
    await query.message.reply("Новая дата отказа (ГГГГ-ММ-ДД):")
    await state.set_state(SettingsState.quit_date)

@settings_router.message(SettingsState.quit_date)
async def save_quit_date(message: Message, state: FSMContext):
    try:
        quit_date = date.fromisoformat(message.text)
    except ValueError:
        await message.reply("Неверный формат! ГГГГ-ММ-ДД.")
        return
    await update_user(message.from_user.id, quit_date=quit_date)
    await message.reply("Дата обновлена! 📅")
    await state.clear()

@settings_router.callback_query(F.data == "toggle_notifs")
async def toggle_notifs(query: CallbackQuery):
    user = await get_user(query.from_user.id)
    new_enabled = not user.notifications_enabled
    await update_user(query.from_user.id, notifications_enabled=new_enabled)
    status = 'включены' if new_enabled else 'выключены'
    await query.message.edit_text(f"Уведомления {status}! 🔕")

@settings_router.callback_query(F.data == "edit_period")
async def edit_period(query: CallbackQuery, state: FSMContext):
    await query.message.reply("Новый период уведомлений (дней, напр. 7):")
    await state.set_state(SettingsState.period)

@settings_router.message(SettingsState.period)
async def save_period(message: Message, state: FSMContext):
    try:
        period = int(message.text)
        if period < 1:
            raise ValueError
    except ValueError:
        await message.reply("Неверно! Положительное число.")
        return
    await update_user(message.from_user.id, notification_period=period)
    await message.reply("Период обновлён! ⏰")
    await state.clear()