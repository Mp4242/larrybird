# handlers/post.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from database.user import User 
from database.post import Post
from database.utils import (
    get_user,
    get_posts_by_user,
    get_post_by_id,
    update_post,
)
from config import SUPER_GROUP, TOPICS

posts_router = Router()

# ─── Helpers ---------------------------------------------------------------
from aiogram.exceptions import TelegramForbiddenError

async def warn_private(bot, tg_id: int, text: str) -> None:
    try:
        await bot.send_message(tg_id, text)
    except TelegramForbiddenError:
        pass

async def profile_ok(user: User | None, bot, tg_id: int) -> bool:
    if not user or not user.pseudo or not user.avatar_emoji:
        await warn_private(bot, tg_id,
                           "⚠️ Сначала создай профиль → /start")
        return False
    return True

# /posts  ou  /myposts
@posts_router.message(F.text.in_(("/myposts", "/posts")))
async def cmd_myposts(msg: Message):
    user = await get_user(msg.from_user.id)
    if not user:
        return await msg.answer("❌ Сначала создай профиль: /start")

    posts = await get_posts_by_user(user.id, only_original=True)
    if not posts:
        return await msg.answer("У тебя пока нет сообщений.")

    for p in posts:
        header  = f"#{p.id} · {p.created_at:%d.%m.%Y}"
        preview = p.text[:100] + ("…" if len(p.text) > 100 else "")
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"del:{p.id}")]
        ])
        await msg.answer(f"{header}\n\n{preview}", reply_markup=kb)


# ─────────── Confirmation suppression ───────────
@posts_router.callback_query(F.data.startswith("del:"))
async def confirm_delete(cb: CallbackQuery):
    post_id = int(cb.data.split(":", 1)[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да",  callback_data=f"del_yes:{post_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data="del_no")
    ]])
    await cb.message.edit_text(f"⚠️ Удалить пост #{post_id} и все ответы ?", reply_markup=kb)
    await cb.answer()


# ─────────── Suppression (soft-delete) ───────────
# suppression
@posts_router.callback_query(F.data.startswith("del_yes:"))
async def delete_post(cb: CallbackQuery):
    post_id = int(cb.data.split(":", 1)[1])
    post = await get_post_by_id(post_id)
    if not post or post.deleted:
        return await cb.answer("Пост уже удалён.", show_alert=True)

    # soft-delete DB
    await update_post(post_id, deleted=True)

    # soft-delete visuel
    await cb.bot.edit_message_text(chat_id=SUPER_GROUP, message_id=post_id, text="(удалено)")

    await cb.answer("✅ Пост удалён", show_alert=True)
    await cb.message.delete()   # retire la carte

# annulation
@posts_router.callback_query(F.data == "del_no")
async def cancel_del(cb: CallbackQuery):
    await cb.message.delete()   # on supprime la carte, sans popup
