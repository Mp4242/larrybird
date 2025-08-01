# handlers/settings.py
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date

from database.utils import get_user, update_user

settings_router = Router()

# ────────────── FSM (champs éditables) ──────────────
class SettingsState(StatesGroup):
    pseudo      = State()
    emoji       = State()
    quit_date   = State()
    period      = State()      # période d’auto-rappel, en jours

# ────────────── /settings ──────────────
@settings_router.message(Command("settings"))
async def settings_handler(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        return await message.reply("❌ Профиль не найден. Сначала /start!")

    # champs optionnels → valeurs par défaut
    notif_enabled = getattr(user, "notifications_enabled", True)
    notif_period  = getattr(user, "notification_period", 7)

    text = (
        "⚙️ <b>Текущие настройки</b>\n"
        f"• Псевдоним: <code>{user.pseudo}</code>\n"
        f"• Эмодзи: {user.avatar_emoji}\n"
        f"• Дата отказа: {user.quit_date or '—'}\n"
        f"• Уведомления: {'Вкл' if notif_enabled else 'Выкл'}\n"
        f"• Период напоминаний: {notif_period} дн."
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("✏️ Псевдоним",  callback_data="edit_pseudo")],
        [InlineKeyboardButton("🙂 Эмодзи",     callback_data="edit_emoji")],
        [InlineKeyboardButton("📅 Дата отказа", callback_data="edit_quit_date")],
        [InlineKeyboardButton("🔔 Вкл/Выкл",   callback_data="toggle_notifs")],
        [InlineKeyboardButton("⏰ Период",      callback_data="edit_period")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

# ────────────── PSEUDO ──────────────
@settings_router.callback_query(F.data == "edit_pseudo")
async def ask_pseudo(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("✏️ Введите новый псевдоним (1-30 символов):")
    await state.set_state(SettingsState.pseudo)
    await cb.answer()

@settings_router.message(SettingsState.pseudo)
async def save_pseudo(msg: Message, state: FSMContext):
    pseudo = msg.text.strip()
    if not 1 <= len(pseudo) <= 30:
        return await msg.answer("❌ Неверно. 1-30 символов, без пробелов.")
    await update_user(msg.from_user.id, pseudo=pseudo)
    await msg.answer("✅ Псевдоним обновлён!")
    await state.clear()

# ────────────── EMOJI ──────────────
EMOJIS = ["👤", "😎", "🐶", "🐱", "🦁", "🐺"]

@settings_router.callback_query(F.data == "edit_emoji")
async def choose_emoji(cb: CallbackQuery, state: FSMContext):
    rows = [[InlineKeyboardButton(e, callback_data=f"set_emoji:{e}")]
            for e in EMOJIS]
    await cb.message.edit_text("🙂 Выберите эмодзи:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()

@settings_router.callback_query(F.data.startswith("set_emoji:"))
async def save_emoji(cb: CallbackQuery, state: FSMContext):
    emoji = cb.data.split(":")[1]
    await update_user(cb.from_user.id, avatar_emoji=emoji)
    await cb.message.edit_text("✅ Эмодзи обновлён!")
    await cb.answer()

# ────────────── QUIT DATE ──────────────
@settings_router.callback_query(F.data == "edit_quit_date")
async def ask_date(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("📅 Новая дата (ГГГГ-ММ-ДД) или 0 — чтобы очистить:")
    await state.set_state(SettingsState.quit_date)
    await cb.answer()

@settings_router.message(SettingsState.quit_date)
async def save_date(msg: Message, state: FSMContext):
    raw = msg.text.strip()
    if raw == "0":
        await update_user(msg.from_user.id, quit_date=None)
        await msg.answer("✅ Дата очищена.")
    else:
        try:
            qd = date.fromisoformat(raw)
        except ValueError:
            return await msg.answer("❌ Формат: ГГГГ-ММ-ДД. Попробуйте ещё.")
        await update_user(msg.from_user.id, quit_date=qd)
        await msg.answer("✅ Дата обновлена.")
    await state.clear()

# ────────────── NOTIFICATIONS ON/OFF ──────────────
@settings_router.callback_query(F.data == "toggle_notifs")
async def toggle_notifs(cb: CallbackQuery):
    user = await get_user(cb.from_user.id)
    enabled = not getattr(user, "notifications_enabled", True)
    await update_user(cb.from_user.id, notifications_enabled=enabled)
    await cb.answer(f"🔔 Уведомления {'включены' if enabled else 'выключены'}", show_alert=True)
    await cb.message.delete()

# ────────────── PERIOD ──────────────
@settings_router.callback_query(F.data == "edit_period")
async def ask_period(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("⏰ Новый период (дней, например 7):")
    await state.set_state(SettingsState.period)
    await cb.answer()

@settings_router.message(SettingsState.period)
async def save_period(msg: Message, state: FSMContext):
    try:
        days = int(msg.text.strip())
        if days < 1:
            raise ValueError
    except ValueError:
        return await msg.answer("❌ Введите положительное число.")
    await update_user(msg.from_user.id, notification_period=days)
    await msg.answer("✅ Период обновлён.")
    await state.clear()
