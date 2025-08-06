# handlers/main.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
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

# ═══════════════════════════  FSM  ═══════════════════════════
class SosState(StatesGroup):
    waiting_for_text = State()
class WinState(StatesGroup):
    waiting_for_text = State()

# ═════════════  UI helper (1 seule fonction)  ══════════════
def post_inline_keyboard(
    *,
    message_id: int,
    with_reply: bool   = True,
    with_like: bool    = True,
    with_support: bool = False,
    likes: int = 0
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

# ═════════════  Outils divers  ══════════════
def format_sobriety_duration(start_date: date | None) -> str:
    if not start_date:
        return "ещё не начал"
    delta = date.today() - start_date
    y, r = divmod(delta.days, 365)
    m, d = divmod(r, 30)
    parts = [f"{y} г." if y else "", f"{m} мес." if m else "", f"{d} дн." if d else ""]
    return " ".join(p for p in parts if p)

async def ensure_profile_complete(user: User | None, reply_fn):
    if not user or not user.pseudo or not user.avatar_emoji:
        await reply_fn("⚠️ Профиль не завершён. Напиши /start.")
        return False
    return True

# ═════════════  /win – /sos  ══════════════
@main_router.message(F.text == "/win")
async def cmd_win(msg: Message, state: FSMContext):
    async with async_session() as ses:
        user = await ses.scalar(select(User).where(User.telegram_id == msg.from_user.id))
        if not await ensure_profile_complete(user, msg.answer):
            return
    await msg.answer("🎉 Расскажи о своей победе (до 500 символов):")
    await state.set_state(WinState.waiting_for_text)

@main_router.message(F.text == "/sos")
async def cmd_sos(msg: Message, state: FSMContext):
    async with async_session() as ses:
        user = await ses.scalar(select(User).where(User.telegram_id == msg.from_user.id))
        if not await ensure_profile_complete(user, msg.answer):
            return
    await msg.answer("🆘 Что случилось? Опиши свою ситуацию (до 500 символов):")
    await state.set_state(SosState.waiting_for_text)

# Annulation si l’utilisateur tape une /commande en plein saisie
@main_router.message(StateFilter(SosState.waiting_for_text), F.text.startswith("/"))
@main_router.message(StateFilter(WinState.waiting_for_text), F.text.startswith("/"))
async def cancel_post(msg: Message, state: FSMContext):
    await state.clear()

# ═════════════  Publication SOS  ══════════════
@main_router.message(StateFilter(SosState.waiting_for_text))
async def handle_sos_text(msg: Message, state: FSMContext):
    if not msg.text:
        return
    text = msg.text.strip()[:500]

    async with async_session() as ses:
        user: User = await ses.scalar(select(User).where(User.telegram_id == msg.from_user.id))
        if not await ensure_profile_complete(user, msg.answer):
            return

        sobriety = format_sobriety_duration(user.quit_date)
        full_text = (
            f"{text}\n\n"
            f"—\n{user.avatar_emoji} {user.pseudo}  | {sobriety}  | 0 ответов"
        )

        sent = await msg.bot.send_message(
            SUPER_GROUP,
            message_thread_id=TOPICS["sos"],
            text=full_text
        )

        await msg.bot.edit_message_reply_markup(
            SUPER_GROUP, sent.message_id,
            reply_markup=post_inline_keyboard(message_id=sent.message_id,
                                              with_reply=True,
                                              with_like=True,
                                              with_support=True,
                                              likes=0)
        )

        ses.add(Post(id=sent.message_id, author_id=user.id,
                     thread_id=TOPICS["sos"], text=text))
        await ses.commit()

    await msg.answer("✅ Сообщение опубликовано анонимно.")
    await state.clear()

# ═════════════  Publication WIN  ══════════════
@main_router.message(StateFilter(WinState.waiting_for_text))
async def handle_win_text(msg: Message, state: FSMContext):
    if not msg.text:
        return
    text = msg.text.strip()[:500]

    async with async_session() as ses:
        user: User = await ses.scalar(select(User).where(User.telegram_id == msg.from_user.id))
        if not await ensure_profile_complete(user, msg.answer):
            return

        sobriety = format_sobriety_duration(user.quit_date)
        full_text = (
            f"{text}\n\n"
            f"—\n{user.avatar_emoji} {user.pseudo}  | {sobriety}  | 0 ответов"
        )

        sent = await msg.bot.send_message(
            SUPER_GROUP,
            message_thread_id=TOPICS["wins"],
            text=full_text
        )
        await msg.bot.edit_message_reply_markup(
            SUPER_GROUP, sent.message_id,
            reply_markup=post_inline_keyboard(message_id=sent.message_id,
                                              with_reply=True,
                                              with_like=True,
                                              with_support=False,
                                              likes=0)
        )

        ses.add(Post(id=sent.message_id, author_id=user.id,
                     thread_id=TOPICS["wins"], text=text))
        await ses.commit()

    await msg.answer("✅ Победа опубликована!")
    await state.clear()

# ═════════════  Publication ANNOUNCES  (exemple) ══════════════
# Utilise with_reply=False & with_support=False
async def publish_announce(bot, text: str):
    sent = await bot.send_message(
        SUPER_GROUP,
        message_thread_id=TOPICS["announces"],
        text=text
    )
    await bot.edit_message_reply_markup(
        SUPER_GROUP, sent.message_id,
        reply_markup=post_inline_keyboard(message_id=sent.message_id,
                                          with_reply=False,
                                          with_like=True,
                                          with_support=False,
                                          likes=0)
    )

# ═════════════  Like ❤️  ══════════════
@main_router.callback_query(F.data.startswith("like:"))
async def like_post(cb: CallbackQuery):
    post_id = int(cb.data.split(":", 1)[1])

    async with async_session() as ses:
        # déjà liké ?
        already = await ses.scalar(select(PostLike)
                                   .where(PostLike.post_id == post_id,
                                          PostLike.user_id == cb.from_user.id))
        if already:
            return await cb.answer("Уже лайкнул 😉", show_alert=True)

        ses.add(PostLike(post_id=post_id, user_id=cb.from_user.id))
        await ses.commit()

        likes = await ses.scalar(
            select(func.count()).select_from(PostLike)
                  .where(PostLike.post_id == post_id)
        )

    # type de thread -> quels boutons afficher
    thread_id = cb.message.message_thread_id
    with_support = thread_id == TOPICS["sos"]
    with_reply   = with_support or thread_id == TOPICS["wins"]

    await cb.message.edit_reply_markup(
        post_inline_keyboard(message_id=post_id,
                             with_reply=with_reply,
                             with_like=True,
                             with_support=with_support,
                             likes=likes)
    )
    await cb.answer("❤️")

# ═════════════  Bouton « 🤝 Поддержать »  ══════════════
@main_router.callback_query(F.data.startswith("support:"))
async def handle_support(cb: CallbackQuery):
    if cb.from_user.id not in MENTORS:
        return await cb.answer("⛔ Только для наставников", show_alert=True)
    await cb.answer("✅ Ты поддержал участника!")
