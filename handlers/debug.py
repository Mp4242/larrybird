from aiogram import Router
from aiogram.types import Message
from config import SUPER_GROUP

debug_router = Router()

@debug_router.message()
async def show_thread_id(msg: Message):
    if msg.chat.id == SUPER_GROUP:
        await msg.answer(f"thread_id = {msg.message_thread_id}")
