from aiogram import Router, F
from aiogram.types import Message
from database.utils import get_user

help_router = Router()

@help_router.message(F.text == "/help")
async def cmd_help(msg: Message):
    user = await get_user(msg.from_user.id)
    if not user or not user.is_member:
        return await msg.answer("❌ Нет доступа. Сначала оплати подписку → /start")
    await msg.answer(
        "/sos – написать SOS\n"
        "/win – поделиться победой\n"
        "/counter – мой счётчик\n"
        "/posts – мои посты\n"
        "/settings – настройки\n"
        "/call – запрос созвона с ментором",
        parse_mode="HTML",
    )