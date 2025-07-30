# handlers/myposts.py
import math, logging
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from database.database import async_session
from database.post import Post
from database.user import User
from config import SUPER_GROUP

myposts_router = Router()
logging.basicConfig(level=logging.INFO)

POSTS_PER_PAGE = 5           # pagination simple

class DelState(StatesGroup):
    waiting_confirm = State()        # awaiting Yes / No

# ---------- /myposts -----------------------------------------------------
@myposts_router.message(F.chat.type == "private", F.text == "/myposts")
async def cmd_myposts(msg: Message):
    page = 1
    await _send_page(msg, msg.from_user.id, page)

async def _send_page(msg: Message, tg_id: int, page: int):
    async with async_session() as ses:
        user = await ses.scalar(select(User).where(User.telegram_id == tg_id))
        if not user:
            return await msg.answer("❌ Профиль не найден. /start")

        q = select(Post).where(Post.author_id == user.id, Post.is_deleted.is_(False))
        total = (await ses.execute(q)).scalars().count()
        pages = max(1, math.ceil(total / POSTS_PER_PAGE))

        # slice
        posts = (
            await ses.execute(
                q.order_by(Post.created_at.desc())
                 .offset((page-1)*POSTS_PER_PAGE)
                 .limit(POSTS_PER_PAGE)
            )
        ).scalars().all()

    if not posts:
        return await msg.answer("У тебя пока нет постов.")

    lines, kb_rows = [], []
    for p in posts:
        excerpt = (p.text[:70] + "…") if len(p.text) > 70 else p.text
        lines.append(f"#{p.id} • {excerpt}")
        kb_rows.append([
            InlineKeyboardButton("🗑️ Удалить", callback_data=f"del:{p.id}")
        ])

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"mypg:{page-1}"))
    if page < pages:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"mypg:{page+1}"))
    if nav:
        kb_rows.append(nav)

    await msg.answer(
        "Твои посты:\n" + "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows)
    )

# ---------- pagination callback -----------------------------------------
@myposts_router.callback_query(F.data.startswith("mypg:"))
async def myposts_page(cb: CallbackQuery):
    page = int(cb.data.split(":",1)[1])
    await cb.answer()
    await _send_page(cb.message, cb.from_user.id, page)
    await cb.message.delete()

# ---------- supprimer : demande de conf ---------------------------------
@myposts_router.callback_query(F.data.startswith("del:"))
async def ask_delete(cb: CallbackQuery, state: FSMContext):
    post_id = int(cb.data.split(":",1)[1])
    await state.set_state(DelState.waiting_confirm)
    await state.update_data(target_id=post_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("✅ Oui",  callback_data="del_yes"),
            InlineKeyboardButton("❌ Non", callback_data="del_no"),
        ]
    ])
    await cb.answer()
    await cb.message.answer(
        "⚠️ Удаление нельзя отменить и закроет весь тред.\nУдалить?",
        reply_markup=kb
    )

# ---------- conf NON -----------------------------------------------------
@myposts_router.callback_query(DelState.waiting_confirm, F.data == "del_no")
async def del_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.answer("Отменено.", show_alert=True)
    await cb.message.delete()

# ---------- conf OUI  → soft delete -------------------------------------
@myposts_router.callback_query(DelState.waiting_confirm, F.data == "del_yes")
async def del_execute(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    post_id = data.get("target_id")
    uid = cb.from_user.id

    async with async_session() as ses:
        user = await ses.scalar(select(User).where(User.telegram_id == uid))
        post = await ses.get(Post, post_id)

        if not post or post.author_id != user.id or post.is_deleted:
            await cb.answer("❌ Не могу удалить.", show_alert=True)
            await state.clear()
            return

        # 1. flag DB
        post.is_deleted = True
        await ses.commit()

    # 2. edit TG message – remplacer texte + retirer boutons
    try:
        await cb.bot.edit_message_text(
            chat_id=SUPER_GROUP,
            message_id=post_id,
            text="(удалено)"
        )
    except Exception as e:
        logging.warning(f"[DEL] TG edit fail: {e}")

    await state.clear()
    await cb.answer("Удалено.", show_alert=True)
    await cb.message.delete()
