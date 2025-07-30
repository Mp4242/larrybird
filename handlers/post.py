# handlers/post.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy import select

from database.utils import (
    get_user,
    get_posts_by_user,
    get_post_by_id,
    update_post,
)
from database.post import Post
from handlers.main import post_inline_keyboard, format_sobriety_duration
from config import SUPER_GROUP

posts_router = Router()

# ─────────────────────────  /myposts  ─────────────────────────
@posts_router.message(F.text == "/myposts")
async def cmd_myposts(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    if not user:
        return await msg.answer("❌ Нет профиля. Напиши /start")

    posts = await get_posts_by_user(user.id)
    if not posts:
        return await msg.answer("У тебя пока нет сообщений.")

    for p in posts:
        header = f"#{p.id} · {p.created_at:%d.%m.%Y} · {len(p.text)} симв."
        preview = (p.text[:100] + "…") if len(p.text) > 100 else p.text

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton("🗑️ Удалить", callback_data=f"del:{p.id}")]
            ]
        )
        await msg.answer(f"{header}\n\n{preview}", reply_markup=kb)

# ─────────────────────  Confirmation suppression  ─────────────────────
@posts_router.callback_query(F.data.startswith("del:"))
async def confirm_delete(cb: CallbackQuery, state: FSMContext):
    post_id = int(cb.data.split(":", 1)[1])
    await state.update_data(del_id=post_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data="del_yes"),
                InlineKeyboardButton("❌ Отмена", callback_data="del_no"),
            ]
        ]
    )
    await cb.message.edit_text(
        f"⚠️ Это удалит пост #{post_id} и все ответы.\nПродолжить?",
        reply_markup=kb
    )
    await cb.answer()

# ─────────────────────  Exécution suppression  ─────────────────────
@posts_router.callback_query(F.data == "del_yes")
async def delete_post(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    post_id = data.get("del_id")

    post = await get_post_by_id(post_id)
    if not post:
        return await cb.answer("Пост уже удалён.", show_alert=True)

    # Soft-delete en base
    await update_post(post_id, is_deleted=True)

    # Éditer le message Telegram
    await cb.message.bot.edit_message_text(
        chat_id=SUPER_GROUP,
        message_id=post_id,
        text="(удалено)"
    )

    await cb.answer("✅ Пост удалён.", show_alert=True)
    await state.clear()

@posts_router.callback_query(F.data == "del_no")
async def delete_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer("❌ Отменено", show_alert=True)
