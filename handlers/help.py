from aiogram import Router, F
from aiogram.types import Message

help_router = Router()

@help_router.message(F.text.in_({"/help", "help"}))
async def cmd_help(msg: Message):
    await msg.answer(
        "<b>Команды клуба</b>\n"
        "/sos – 🆘 попросить помощи\n"
        "/win – 🏆 поделиться победой\n"
        "/counter – 📊 мой счётчик дней\n"
        "/posts – 🗑 мои сообщения\n"
        "/settings – ⚙️ настройки профиля",
        parse_mode="HTML",
    )
