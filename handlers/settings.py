# handlers/settings.py
"""Команда /settings : изменить псевдоним, эмодзи, дату отказа и включить/выключить уведомления.
Важно : aiogram v3 → `InlineKeyboardButton` exige des arguments nommés (`text=…`, `callback_data=…`)."""

import re
from datetime import date

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from database.utils import get_user, update_user

settings_router = Router()
PSEUDO_RE = re.compile(r"^(?!/)[^\s]{1,30}$", re.UNICODE)


class SettingsState(StatesGroup):
    pseudo = State()
    emoji = State()
    quit_date = State()


# ─────────────────────────────── /settings ───────────────────────────────
@settings_router.message(Command("settings"))
async def settings_handler(message: Message) -> None:
    user = await get_user(message.from_user.id)
    if not user:
        return await message.reply("❌ Профиль не найден. Сначала /start!")

    notif_enabled = getattr(user, "notifications_enabled", True)

    text = (
        "⚙️ <b>Текущие настройки</b>\n"
        f"• Псевдоним: <code>{user.pseudo}</code>\n"
        f"• Эмодзи: {user.avatar_emoji}\n"
        f"• Дата отказа: {user.quit_date or '—'}\n"
        f"• Уведомления: {'Вкл' if notif_enabled else 'Выкл'}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Псевдоним", callback_data="edit_pseudo")],
            [InlineKeyboardButton(text="🙂 Эмодзи", callback_data="edit_emoji")],
            [InlineKeyboardButton(text="📅 Дата отказа", callback_data="edit_quit_date")],
            [InlineKeyboardButton(text="🔔 Вкл/Выкл", callback_data="toggle_notifs")],
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# ─────────────────────────────── псевдоним ───────────────────────────────
@settings_router.callback_query(F.data == "edit_pseudo")
async def ask_pseudo(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.message.answer("✏️ Введите новый псевдоним (1-30 символов):")
    await state.set_state(SettingsState.pseudo)
    await cb.answer()


@settings_router.message(SettingsState.pseudo)
async def save_pseudo(msg: Message, state: FSMContext) -> None:
    pseudo = msg.text.strip()
    if not PSEUDO_RE.match(pseudo):
        return await msg.answer("❌ Неверно. 1-30 символов, без пробелов.")

    await update_user(msg.from_user.id, pseudo=pseudo)
    await msg.answer("✅ Псевдоним обновлён!")
    await state.clear()


# ─────────────────────────────── эмодзи ───────────────────────────────
EMOJIS = ["👤", "😎", "🐶", "🐱", "🦁", "🐺"]

@settings_router.callback_query(F.data == "edit_emoji")
async def choose_emoji(cb: CallbackQuery, state: FSMContext) -> None:
    rows = [[InlineKeyboardButton(text=e, callback_data=f"set_emoji:{e}")] for e in EMOJIS]
    await cb.message.edit_text("🙂 Выберите эмодзи:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cb.answer()


@settings_router.callback_query(F.data.startswith("set_emoji:"))
async def save_emoji(cb: CallbackQuery, state: FSMContext) -> None:
    emoji = cb.data.split(":", 1)[1]
    await update_user(cb.from_user.id, avatar_emoji=emoji)
    await cb.message.edit_text("✅ Эмодзи обновлён!")
    await cb.answer()


# ─────────────────────────────── дата отказа ───────────────────────────────
@settings_router.callback_query(F.data == "edit_quit_date")
async def ask_date(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.message.answer("📅 Новая дата отказа (ГГГГ-ММ-ДД) или 0 — чтобы очистить:")
    await state.set_state(SettingsState.quit_date)
    await cb.answer()


@settings_router.message(SettingsState.quit_date)
async def save_date(msg: Message, state: FSMContext) -> None:
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


# ─────────────────────────────── уведомления on/off ───────────────────────────────
@settings_router.callback_query(F.data == "toggle_notifs")
async def toggle_notifs(cb: CallbackQuery) -> None:
    user = await get_user(cb.from_user.id)
    enabled = not getattr(user, "notifications_enabled", True)
    await update_user(cb.from_user.id, notifications_enabled=enabled)
    await cb.answer(
        f"🔔 Уведомления {'включены ✅' if enabled else 'выключены ❌'}",
        show_alert=True,
    )
    await cb.message.delete()
