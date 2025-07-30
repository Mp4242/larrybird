from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from datetime import date

from config import SUPER_GROUP, TOPICS, MENTORS
from database.database import async_session
from database.user import User
from database.post import Post

main_router = Router()

# ──────────────────────────────  FSM  ──────────────────────────────
class SosState(StatesGroup):
    waiting_for_text = State()


class WinState(StatesGroup):
    waiting_for_text = State()


# ───────────────────────────  Helpers  ────────────────────────────
def post_inline_keyboard(
    user_id: int,
    message_id: int,
    *,
    disabled: bool = False,
) -> InlineKeyboardMarkup | None:
    """
    Construit les deux boutons sous un post.
    Si disabled=True (post supprimé), renvoie None pour retirer la markup.
    """
    if disabled:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("✍️ Ответить", callback_data=f"reply:{message_id}")],
            [InlineKeyboardButton("🤝 Поддержать", callback_data=f"support:{user_id}")],
        ]
    )


def format_sobriety_duration(start_date: date | None) -> str:
    if not start_date:
        return "ещё не начал"
    delta = date.today() - start_date
    y, r = divmod(delta.days, 365)
    m, d = divmod(r, 30)
    parts = [f"{y} г." if y else "", f"{m} мес." if m else "", f"{d} дн." if d else ""]
    return " ".join(p for p in parts if p)


async def ensure_profile_complete(user: User | None, reply_fn) -> bool:
    if not user or not user.pseudo or not user.avatar_emoji:
        await reply_fn("⚠️ Профиль не завершён. Напиши /start.")
        return False
    return True


# ───────────────────────────  /win  ───────────────────────────────
@main_router.message(F.text == "/win")
async def cmd_win(msg: Message, state: FSMContext):
    async with async_session() as ses:
        user = await ses.scalar(
            select(User).where(User.telegram_id == msg.from_user.id)
        )
        if not await ensure_profile_complete(user, msg.answer):
            return

    await msg.answer("🎉 Расскажи о своей победе (до 500 символов):")
    await state.set_state(WinState.waiting_for_text)


# ───────────────────────────  /sos  ───────────────────────────────
@main_router.message(F.text == "/sos")
async def cmd_sos(msg: Message, state: FSMContext):
    async with async_session() as ses:
        user = await ses.scalar(
            select(User).where(User.telegram_id == msg.from_user.id)
        )
        if not await ensure_profile_complete(user, msg.answer):
            return

    await msg.answer("🆘 Что случилось? Опиши свою ситуацию (до 500 символов):")
    await state.set_state(SosState.waiting_for_text)


# ───── Annuler si l’utilisateur tape une commande pendant la saisie
@main_router.message(StateFilter(SosState.waiting_for_text), F.text.startswith("/"))
@main_router.message(StateFilter(WinState.waiting_for_text), F.text.startswith("/"))
async def cancel_post(msg: Message, state: FSMContext):
    await state.clear()


# ───────────────────  Publication SOS  ────────────────────────────
@main_router.message(StateFilter(SosState.waiting_for_text))
async def handle_sos_text(msg: Message, state: FSMContext):
    if not msg.text:
        return

    text = msg.text.strip()[:500]

    async with async_session() as ses:
        user: User = await ses.scalar(
            select(User).where(User.telegram_id == msg.from_user.id)
        )
        if not await ensure_profile_complete(user, msg.answer):
            return

        sobriety = format_sobriety_duration(user.quit_date)
        full_text = (
            f"{text}\n\n"
            f"—\n{user.avatar_emoji} {user.pseudo}  | {sobriety}  | 0 ответов"
        )

        sent = await msg.bot.send_message(
            chat_id=SUPER_GROUP,
            message_thread_id=TOPICS["sos"],
            text=full_text,
        )
        await sent.edit_reply_markup(
            reply_markup=post_inline_keyboard(user.id, sent.message_id)
        )

        ses.add(
            Post(
                id=sent.message_id,
                author_id=user.id,
                thread_id=TOPICS["sos"],
                text=text,
            )
        )
        await ses.commit()

    await msg.answer("✅ Сообщение опубликовано анонимно.")
    await state.clear()


# ───────────────────  Publication WIN  ────────────────────────────
@main_router.message(StateFilter(WinState.waiting_for_text))
async def handle_win_text(msg: Message, state: FSMContext):
    if not msg.text:
        return

    text = msg.text.strip()[:500]

    async with async_session() as ses:
        user: User = await ses.scalar(
            select(User).where(User.telegram_id == msg.from_user.id)
        )
        if not await ensure_profile_complete(user, msg.answer):
            return

        sobriety = format_sobriety_duration(user.quit_date)
        full_text = (
            f"{text}\n\n"
            f"—\n{user.avatar_emoji} {user.pseudo}  | {sobriety}  | 0 ответов"
        )

        sent = await msg.bot.send_message(
            chat_id=SUPER_GROUP,
            message_thread_id=TOPICS["wins"],
            text=full_text,
        )
        await sent.edit_reply_markup(
            reply_markup=post_inline_keyboard(user.id, sent.message_id)
        )

        ses.add(
            Post(
                id=sent.message_id,
                author_id=user.id,
                thread_id=TOPICS["wins"],
                text=text,
            )
        )
        await ses.commit()

    await msg.answer("✅ Победа опубликована!")
    await state.clear()


# ───────────────────  Support (mentors)  ──────────────────────────
@main_router.callback_query(F.data.startswith("support:"))
async def handle_support(cb: CallbackQuery):
    if cb.from_user.id not in MENTORS:
        return await cb.answer("⛔ Только для наставников", show_alert=True)
    await cb.answer("✅ Ты поддержал участника!")
