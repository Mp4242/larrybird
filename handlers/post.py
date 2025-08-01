# handlers/post.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database.utils import (
    get_user, get_posts_by_user, get_post_by_id, update_post
)
from config import SUPER_GROUP
from database.post import Post

posts_router = Router()

# ──────────── /myposts ─────────────
@posts_router.message(F.text.in_(("/myposts", "/posts")))
async def cmd_myposts(msg: Message):
    user = await get_user(msg.from_user.id)
    if not user:
        return await msg.answer("❌ Нет профиля. Напиши /start")

    posts = await get_posts_by_user(user.id)
    if not posts:
        return await msg.answer("У тебя пока нет опубликованных постов.")

    for p in posts:
        hdr = f"#{p.id} · {p.created_at:%d.%m.%Y}"
        prev = (p.text[:100] + "…") if len(p.text) > 100 else p.text
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"del:{p.id}")]]
        )
        await msg.answer(f"{hdr}\n\n{prev}", reply_markup=kb)

# ───────── Confirmation ──────────
@posts_router.callback_query(F.data.startswith("del:"))
async def confirm_delete(cb: CallbackQuery):
    pid = int(cb.data.split(":", 1)[1])
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton("✅ Да", callback_data=f"del_yes:{pid}"),
            InlineKeyboardButton("❌ Нет", callback_data=f"del_no:{pid}")
        ]]
    )
    await cb.message.edit_text(
        f"⚠️ Удалить пост #{pid} и все ответы?",
        reply_markup=kb
    )
    await cb.answer()

# ───────── Suppression ──────────
@posts_router.callback_query(F.data.startswith("del_yes:"))
async def delete_post(cb: CallbackQuery):
    pid = int(cb.data.split(":", 1)[1])
    post = await get_post_by_id(pid)
    if not post or post.deleted:
        return await cb.answer("Пост уже удалён.", show_alert=True)

    # soft-delete
    await update_post(pid, deleted=True)

    # masque le message public
    await cb.message.bot.edit_message_text(
        chat_id=SUPER_GROUP,
        message_id=pid,
        text="(удалено, кнопки скрыты)"
    )
    await cb.answer("✅ Пост удалён", show_alert=True)
    await cb.message.delete()

@posts_router.callback_query(F.data.startswith("del_no:"))
async def cancel_del(cb: CallbackQuery):
    await cb.answer("❌ Отменено", show_alert=True)
    await cb.message.delete()
