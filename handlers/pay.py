# handlers/pay.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import select
from datetime import datetime, timedelta

from config import TRIBUTE_URL_TEMPLATE
from database.database import async_session
from database.user import User

pay_router = Router()

PAY_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить в Tribute", url=TRIBUTE_URL_TEMPLATE)],
        [InlineKeyboardButton(text="👀 Посмотреть демо", callback_data="demo")],
    ]
)

def pay_text(user: User | None) -> str:
    if user and user.paid_until and user.paid_until > datetime.utcnow():
        left = (user.paid_until - datetime.utcnow()).days
        return f"✅ Подписка активна, осталось ~{left} дн.\nХочешь продлить?"
    return (
        "💳 Доступ к закрытому клубу.\n\n"
        "• SOS и WIN посты в приватном чате\n"
        "• Ответы, поддержка наставников\n"
        "• Личный счётчик и статистика\n\n"
        "Оплата через Tribute:"
    )

@pay_router.callback_query(F.data == "pay")
async def open_pay_cb(cb: CallbackQuery):
    async with async_session() as ses:
        user = await ses.scalar(select(User).where(User.telegram_id == cb.from_user.id))
    await cb.message.answer(pay_text(user), reply_markup=PAY_KB)
    await cb.answer()

@pay_router.message(Command("pay"))
async def open_pay_cmd(msg: Message):
    async with async_session() as ses:
        user = await ses.scalar(select(User).where(User.telegram_id == msg.from_user.id))
    await msg.answer(pay_text(user), reply_markup=PAY_KB)
