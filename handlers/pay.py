# handlers/pay.py
"""Оплата через Tribute (кнопка + веб‑хука).

• Кнопка «💳 Оплатить» открывает Tribute‑checkout с query‑param `uid=<telegram_id>`.
• Webhook (в bot.py) ловит status==paid и добавляет участника в группу.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import TRIBUTE_URL_TEMPLATE  # ex: "https://pay.tribute.co/trezv?uid={uid}"

pay_router = Router()


@pay_router.callback_query(F.data == "pay")
async def pay_link(cb: CallbackQuery):
    url = TRIBUTE_URL_TEMPLATE.format(uid=cb.from_user.id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="💳 Открыть оплату", url=url)]]
    )
    await cb.message.answer(
        "💳 Оплата проходит в браузере. После успешного платежа я добавлю тебя в группу автоматически.",
        reply_markup=kb,
    )
    await cb.answer()
