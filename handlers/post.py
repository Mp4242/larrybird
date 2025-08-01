# handlers/post.py
"""Gestion des posts de l’utilisateur : liste (/posts, /myposts) et soft‑delete.

• Affiche uniquement les posts racine (parent_id == NULL).
• Corrige l’erreur aiogram v3 liée à l’usage positionnel de InlineKeyboardButton.
"""

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
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

# ─────────────────────────  /posts ─────────────────────────
@posts_router.message(F.text.in_({"/posts", "/myposts"}))
async def cmd_posts(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)
    if not user:
        return await msg.answer("❌ Нет профиля. Напиши /start")

    # Récupère uniquement les racines
    posts = await get_posts_by_user(user.id)
    posts = [p for p in posts if getattr(p, "parent_id", None) is None]

    if not posts:
        return await msg.answer("У тебя пока нет постов.")

    for p in posts:
        header = f"#{p.id} · {p.created_at:%d.%m.%Y}"
        preview = p.text if len(p.text) <= 100 else p.text[:100] + "…"

        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"del:{p.id}")]]
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
                InlineKeyboardButton(text="✅ Да, удалить", callback_data="del_yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="del_no"),
            ]
        ]
    )
    await cb.message.edit_text(
        f"⚠️ Это удалит пост #{post_id} и все ответы.\nПродолжить?",
        reply_markup=kb,
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

    # Soft‑delete
    await update_post(post_id, is_deleted=True)

    # Modification du message dans le groupe
    await cb.message.bot.edit_message_text(
        chat_id=SUPER_GROUP,
        message_id=post_id,
        text="(удалено)",
    )

    await cb.answer("✅ Пост удалён.", show_alert=True)
    await state.clear()


# Annuler suppression (callback "del_no")
@posts_router.callback_query(F.data == "del_no")
async def delete_cancel(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    post_id = data.get("del_id")

    post = await get_post_by_id(post_id)
    if not post:
        await cb.answer("Пост не найден.", show_alert=True)
        await state.clear()
        return

    header  = f"#{post.id} · {post.created_at:%d.%m.%Y}"
    preview = post.text if len(post.text) <= 100 else post.text[:100] + "…"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🗑️ Удалить",
                                              callback_data=f"del:{post.id}")]]
    )
    await cb.message.edit_text(f"{header}\n\n{preview}", reply_markup=kb)
    await cb.answer("❌ Отменено")
    await state.clear()
