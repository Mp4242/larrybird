from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

router = Router()

@router.message(CommandStart())
async def start_handler(msg: Message):
    await msg.answer("Добро пожаловать в новую версию TREZV Bot (aiogram 3.x) 🚀")

@router.callback_query(F.data == "sos")
async def sos_handler(callback: CallbackQuery):
    await callback.message.answer("🆘 SOS reçu")
    await callback.answer()