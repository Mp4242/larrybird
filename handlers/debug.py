# handlers/debug.py
from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from datetime import datetime, time, timezone

from config import ADMINS
from database.database import async_session
from database.user import User

debug_router = Router()

class FakePaidState(StatesGroup):
    waiting_for_date = State()

@debug_router.message(F.text == "/fake_paid_until")
async def fake_paid_until_cmd(msg: Message, state: FSMContext):
    # admin-only + do it in DM (so we don't leak anything in the group)
    if msg.from_user.id not in ADMINS:
        return await msg.answer("⛔ Только для админов.")
    if msg.chat.type != "private":
        return await msg.answer("👋 Напиши мне в личку эту команду.")

    await msg.answer("Введите дату окончания в формате ДД.ММ.ГГГГ\nНапример: 14.09.2025\n"
                     "Подсказка: поставь вчерашнюю дату и запусти /cron_expire для теста.")
    await state.set_state(FakePaidState.waiting_for_date)

@debug_router.message(FakePaidState.waiting_for_date)
async def fake_paid_until_set(msg: Message, state: FSMContext):
    raw = (msg.text or "").strip()
    try:
        d = datetime.strptime(raw, "%d.%m.%Y").date()
    except ValueError:
        return await msg.answer("❌ Формат неверный. Пример: 14.09.2025")

    # store as UTC midnight start-of-day
    paid_until_dt = datetime.combine(d, time(0, 0, 0, tzinfo=timezone.utc))

    async with async_session() as ses:
        user: User | None = await ses.scalar(
            select(User).where(User.telegram_id == msg.from_user.id)
        )
        if not user:
            return await msg.answer("❌ Пользователь не найден в базе. Сначала /start.")

        user.paid_until = paid_until_dt
        # set membership based on whether it's still active
        user.is_member = paid_until_dt >= datetime.now(timezone.utc)
        await ses.commit()

    await state.clear()

    status = "активна ✅" if paid_until_dt >= datetime.now(timezone.utc) else "истекла ⛔"
    await msg.answer(
        f"Готово!\npaid_until = {raw}\nПодписка сейчас: {status}\n\n"
        "Чтобы проверить авто-исключение: поставь вчера → запусти /cron_expire."
    )
