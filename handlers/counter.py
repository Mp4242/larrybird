from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime, date
from sqlalchemy import select, func

from config import AVG_HOURS_DAY, AVG_NEURONS_DAY, AVG_COST_DAY
from database.database import async_session
from database.user import User

counter_router = Router()

# ─── FSM ────────────────────────────────────────────────
class CounterState(StatesGroup):
    waiting_date = State()

DATE_FMT = "%d.%m.%Y"

def human_dhms(days: int) -> str:
    y, r = divmod(days, 365)
    m, d = divmod(r, 30)
    return " ".join(f"{n} {u}" for n, u in ((y, "г."), (m, "мес."), (d, "дн.")) if n) or "0 дн."

async def count_currently_sober() -> int:
    async with async_session() as ses:
        res = await ses.execute(
            select(func.count())
            .select_from(User)
            .where(User.quit_date.is_not(None), User.is_sober.is_(True))
        )
        return res.scalar_one()

async def show_stats(user: User, reply):
    days = (date.today() - user.quit_date).days
    total_sober = await count_currently_sober()

    header = f"📊 Сегодня трезвых: <b>{total_sober}</b>"
    body = (
        f"📅 Дата отказа: <b>{user.quit_date:%d.%m.%Y}</b>\n"
        f"⏳ <b>{human_dhms(days)}</b> трезвости\n\n"
        f"🧠 Сохранил нейронов: <b>{days * AVG_NEURONS_DAY:,}</b>\n"
        f"⏲️ Часов ясного сознания: <b>{days * AVG_HOURS_DAY}</b>\n"
        f"💰 Экономия: <b>{days * AVG_COST_DAY} €</b>"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💔 Я сорвался", callback_data="relapse")]
        ]
    )

    await reply(header, parse_mode="HTML")
    await reply(body, parse_mode="HTML", reply_markup=kb)

# ─── /counter ───────────────────────────────────────────
@counter_router.message(F.text == "/counter")
async def cmd_counter(msg: Message, state: FSMContext):
    uid = msg.from_user.id
    async with async_session() as ses:
        user = (await ses.execute(select(User).where(User.telegram_id == uid))).scalar_one_or_none()

    if not user:
        return await msg.answer("❌ Профиль не найден. Напиши /start.")

    if not user.quit_date:
        await msg.answer("📅 Введи дату отказа (ДД.ММ.ГГГГ):")
        await state.set_state(CounterState.waiting_date)
        return

    await show_stats(user, msg.answer)

@counter_router.message(StateFilter(CounterState.waiting_date))
async def save_date(msg: Message, state: FSMContext):
    try:
        qd = datetime.strptime(msg.text.strip(), DATE_FMT).date()
    except ValueError:
        return await msg.answer("❌ Формат неверный. Пример: 14.06.2024")

    async with async_session() as ses:
        user = (await ses.execute(select(User).where(User.telegram_id == msg.from_user.id))).scalar_one_or_none()
        if not user:
            user = User(telegram_id=msg.from_user.id, pseudo="Аноним")
            ses.add(user)

        user.quit_date = qd
        user.is_sober = True
        user.last_checkpoint = 0
        await ses.commit()

    await state.clear()
    await msg.answer("✅ Дата сохранена!")
    await show_stats(user, msg.answer)

# ─── RELAPSE ────────────────────────────────────────────
@counter_router.callback_query(F.data == "relapse")
async def relapse_menu(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Начать заново", callback_data="relapse_reset")],
            [InlineKeyboardButton(text="🤫 Забыть об этом", callback_data="relapse_forget")],
        ]
    )
    await cb.message.edit_text(
        "Случилось? Не беда. Как поступим?",
        reply_markup=kb
    )

@counter_router.callback_query(F.data == "relapse_reset")
async def relapse_reset(cb: CallbackQuery):
    today = date.today()
    async with async_session() as ses:
        user = (await ses.execute(select(User).where(User.telegram_id == cb.from_user.id))).scalar_one_or_none()
        if user:
            user.quit_date = today
            user.is_sober = True
            user.last_checkpoint = 0
            await ses.commit()
    await cb.message.edit_text("🔄 Счётчик обнулён. Встаём и идём дальше!")

@counter_router.callback_query(F.data == "relapse_forget")
async def relapse_forget(cb: CallbackQuery):
    await cb.message.edit_text("🤫 Ок, это был всего лишь сон. Просто продолжаем!")
