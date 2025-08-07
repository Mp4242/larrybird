# handlers/main.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func
from datetime import date

from config import SUPER_GROUP, TOPICS, MENTORS
from database.database import async_session
from database.user import User
from database.post import Post
from database.post_like import PostLike

main_router = Router()

# ═════════════════════════  FSM  ═════════════════════════
class SosState(StatesGroup):
    waiting_for_text = State()
class WinState(StatesGroup):
    waiting_for_text = State()

# ═════════════  Génération clavier  ═════════════
def post_inline_keyboard(
    *,
    message_id: int,
    with_reply:   bool = True,
    with_like:    bool = True,
    with_support: bool = False,
    likes: int = 0,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if with_reply:
        rows.append([InlineKeyboardButton(
            text="✍️ Ответить", callback_data=f"reply:{message_id}")])

    if with_support:
        rows.append([InlineKeyboardButton(
            text="🤝 Поддержать", callback_data=f"support:{message_id}")])

    if with_like:
        heart = f"❤️ {likes}" if likes else "❤️"
        rows.append([InlineKeyboardButton(
            text=heart, callback_data=f"like:{message_id}")])

    return InlineKeyboardMarkup(inline_keyboard=rows)

# ═════════════  Helpers  ═════════════
def format_sobriety_duration(start: date | None) -> str:
    if not start:
        return "ещё не начал"
    days = (date.today() - start).days
    y, r = divmod(days, 365)
    m, d = divmod(r, 30)
    return " ".join(p for p in (
        f"{y} г." if y else "",
        f"{m} мес." if m else "",
        f"{d} дн." if d else "",
    ) if p)

async def ensure_profile_complete(user: User | None, reply_fn) -> bool:
    if not user or not user.pseudo or not user.avatar_emoji:
        await reply_fn("⚠️ Профиль не завершён. Напиши /start.")
        return False
    return True

# ═════════════  /win et /sos  ═════════════
@main_router.message(F.text == "/win")
async def cmd_win(msg: Message, state: FSMContext):
    async with async_session() as ses:
        user = await ses.scalar(select(User)
                                .where(User.telegram_id == msg.from_user.id))
        if not await ensure_profile_complete(user, msg.answer):
            return
    await msg.answer("🎉 Расскажи о своей победе (до 500 символов):")
    await state.set_state(WinState.waiting_for_text)

@main_router.message(F.text == "/sos")
async def cmd_sos(msg: Message, state: FSMContext):
    async with async_session() as ses:
        user = await ses.scalar(select(User)
                                .where(User.telegram_id == msg.from_user.id))
        if not await ensure_profile_complete(user, msg.answer):
            return
    await msg.answer("🆘 Что случилось? Опиши ситуацию (до 500 символов):")
    await state.set_state(SosState.waiting_for_text)

# — Annulation si /commande pendant la saisie —
@main_router.message(StateFilter(SosState.waiting_for_text), F.text.startswith("/"))
async def cancel_sos(msg: Message, state: FSMContext):
    await state.clear()

@main_router.message(StateFilter(WinState.waiting_for_text), F.text.startswith("/"))
async def cancel_win(msg: Message, state: FSMContext):
    await state.clear()

# ═════════════  Publication SOS  ═════════════
@main_router.message(StateFilter(SosState.waiting_for_text))
async def handle_sos(msg: Message, state: FSMContext):
    if not msg.text:
        return
    text = msg.text.strip()[:500]

    async with async_session() as ses:
        user: User = await ses.scalar(select(User)
                                      .where(User.telegram_id == msg.from_user.id))
        if not await ensure_profile_complete(user, msg.answer):
            return

        sobriety = format_sobriety_duration(user.quit_date)
        body = (
            f"{text}\n\n"
            f"—\n{user.avatar_emoji} {user.pseudo} | {sobriety} | 0 ответов"
        )

        # on envoie sans clavier puis on le rajoute
        # ───── SOS ─────────────────────────────────────────
        sent = await msg.bot.send_message(
            SUPER_GROUP, message_thread_id=TOPICS["sos"], text=body
        )
        await sent.edit_reply_markup(                # ⬅️ AVANT
            reply_markup=post_inline_keyboard(       # ⬅️ APRÈS — on nomme l’arg
                message_id=sent.message_id,
                with_reply=True, with_like=True, with_support=True, likes=0
            )
        )
        ses.add(Post(id=sent.message_id, author_id=user.id,
                     thread_id=TOPICS["sos"], text=text))
        await ses.commit()

    await msg.answer("✅ Сообщение опубликовано анонимно.")
    await state.clear()

# ═════════════  Publication WIN  ═════════════
@main_router.message(StateFilter(WinState.waiting_for_text))
async def handle_win(msg: Message, state: FSMContext):
    if not msg.text:
        return
    text = msg.text.strip()[:500]

    async with async_session() as ses:
        user: User = await ses.scalar(select(User)
                                      .where(User.telegram_id == msg.from_user.id))
        if not await ensure_profile_complete(user, msg.answer):
            return

        sobriety = format_sobriety_duration(user.quit_date)
        body = (
            f"{text}\n\n"
            f"—\n{user.avatar_emoji} {user.pseudo} | {sobriety} | 0 ответов"
        )

        # ───── WIN ─────────────────────────────────────────
        sent = await msg.bot.send_message(
            SUPER_GROUP, message_thread_id=TOPICS["wins"], text=body
        )
        await sent.edit_reply_markup(                # ⬅️ même correction
            reply_markup=post_inline_keyboard(
                message_id=sent.message_id,
                with_reply=True, with_like=True, with_support=False, likes=0
            )
        )

        ses.add(Post(id=sent.message_id, author_id=user.id,
                     thread_id=TOPICS["wins"], text=text))
        await ses.commit()

    await msg.answer("✅ Победа опубликована!")
    await state.clear()

# ═════════════  Like ❤️  ═════════════
@main_router.callback_query(F.data.startswith("like:"))
async def like_post(cb: CallbackQuery):
    post_id = int(cb.data.split(":", 1)[1])

    async with async_session() as ses:
        # déjà liké ?
        exists = await ses.scalar(select(PostLike)
                                  .where(PostLike.post_id == post_id,
                                         PostLike.user_id == cb.from_user.id))
        if exists:
            return await cb.answer("Уже лайкнул 😉", show_alert=True)

        ses.add(PostLike(post_id=post_id, user_id=cb.from_user.id))
        await ses.commit()

        likes = await ses.scalar(
            select(func.count()).select_from(PostLike)
                  .where(PostLike.post_id == post_id)
        )

    # boutons selon le topic
    thread = cb.message.message_thread_id
    with_support = thread == TOPICS["sos"]
    with_reply   = with_support or thread == TOPICS["wins"]

    try:
        await cb.message.edit_reply_markup(
            reply_markup=post_inline_keyboard(
                message_id=post_id,
                with_reply=with_reply,
                with_like=True,
                with_support=with_support,
                likes=likes
            )
        )
    except Exception:                # BadRequest : « message is not modified »
        pass
    await cb.answer("❤️")

# ═════════════  Bouton « 🤝 Поддержать »  ═════════════
@main_router.callback_query(F.data.startswith("support:"))
async def handle_support(cb: CallbackQuery):
    if cb.from_user.id not in MENTORS:
        return await cb.answer("⛔ Только для наставников", show_alert=True)
    await cb.answer("✅ Ты поддержал участника!")
