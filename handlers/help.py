from aiogram import Router, F
from aiogram.types import Message
from database.utils import get_user

help_router = Router()

@help_router.message(F.text.in_({"/help", "help"}))
async def cmd_help(msg: Message):
    user = await get_user(msg.from_user.id)

    # profil inexistant OU encore « _anon… » → pas d’accès
    if not user or user.pseudo.startswith("_anon"):
        return await msg.answer("❌ Сначала создай профиль → /start")

    # profil ok → liste des commandes
    await msg.answer(
        "<b>Команды клуба</b>\n"
        "/sos – 🆘 попросить помощи\n"
        "/win – 🏆 поделиться победой\n"
        "/counter – 📊 мой счётчик дней\n"
        "/posts – 🗑 мои сообщения\n"
        "/settings – ⚙️ настройки профиля",
        parse_mode="HTML",
    )
