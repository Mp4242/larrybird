from __future__ import annotations

# handlers/onboarding.py
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from datetime import datetime
import re

from database.database import async_session
from database.user import User
from database.utils import get_user, free_slots_left          # utils déjà présents
#  ───────────────────────────────────────────────────────────

onboarding_router = Router()

# ═════ FSM ═════
class OnboardingState(StatesGroup):
    pseudo       = State()
    emoji        = State()
    choose_date  = State()
    typing_date  = State()

# ═════ Constantes UI ═════
EMOJI_CHOICES = ["😎", "👤", "🦁", "🐺", "🦅",
                 "🐯", "🔥", "💪", "🥷", "👽"]
PSEUDO_RE     = re.compile(r"^(?!/)\S{1,30}$", re.UNICODE)

DATE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton("🗓️ Указать дату", callback_data="set_date")],
        [InlineKeyboardButton("⏭️ Укажу позже",  callback_data="skip_date")]
    ]
)

WELCOME_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton("💳 Вступить за 100 ₽", callback_data="pay")],
        [InlineKeyboardButton("👀 Посмотреть демо",    callback_data="demo")]
    ]
)

# ═════════════════════════════ /start
@onboarding_router.message(F.text == "/start")
async def cmd_start(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)

    # ① Pas encore dans la DB → proposer gratuit/payant
    if not user:
        slots = await free_slots_left()
        if slots:      # places gratuites restantes
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(
                        f"🎁 Войти бесплатно · осталось {slots}",
                        callback_data="join_free")],
                    [InlineKeyboardButton("👀 Посмотреть демо",
                                          callback_data="demo")]
                ]
            )
            return await msg.answer(
                "🔥 Приватный клуб TREZV\n"
                "Первые 100 получают доступ навсегда.\n"
                f"Осталось <b>{slots}</b> мест 👇",
                reply_markup=kb, parse_mode="HTML"
            )
        # plus de places -> payant
        return await msg.answer(
            "🔥 Приватный клуб TREZV.\nСмотри демо или вступай 👇",
            reply_markup=WELCOME_KB
        )

    # ② Dans la DB mais profil stub (_anon…)
    if user.pseudo.startswith("_anon"):
        await msg.answer("✏️ Введи псевдоним (1–30 символов):")
        return await state.set_state(OnboardingState.pseudo)

    # ③ Profil complet -> accueil
    await msg.answer("👋 Ты уже в клубе. /help — список команд.")

# ═════ CALLBACK « join_free » ═════
@onboarding_router.callback_query(F.data == "join_free")
async def join_free(cb: CallbackQuery):
    telegram_id = cb.from_user.id
    slots = await free_slots_left()
    if not slots:
        await cb.answer("Увы, бесплатные места закончились.", show_alert=True)
        # refresh interface
        await cmd_start(cb.message, FSMContext(cb.message.bot, telegram_id))
        return

    async with async_session() as ses:
        user: User | None = await ses.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )
        if user is None:               # on crée
            ses.add(User(
                telegram_id     = telegram_id,
                pseudo          = f"_anon{telegram_id}",
                avatar_emoji    = "👤",
                is_member       = True,
                lifetime_access = True
            ))
        else:                          # déjà stub (rare) -> upgrade
            user.is_member       = True
            user.lifetime_access = True
            if user.pseudo == "":
                user.pseudo = f"_anon{telegram_id}"
        await ses.commit()

    await cb.message.answer(
        "🎉 Ты вошёл в первые 100! Доступ навсегда.\n"
        "Заполни профиль → /start"
    )
    await cb.answer()

# ═════ PSEUDO ═════
@onboarding_router.message(
    StateFilter(OnboardingState.pseudo) & F.text.startswith("/")
)
async def cancel_pseudo(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("Онбординг прерван. Запусти /start заново.")

@onboarding_router.message(StateFilter(OnboardingState.pseudo))
async def set_pseudo(message: Message, state: FSMContext):
    raw = message.text.strip()
    if not PSEUDO_RE.match(raw):
        return await message.answer("❌ 1–30 символов, без пробелов. Попробуй ещё:")
    await state.update_data(pseudo=raw)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(e, callback_data=f"avatar:{e}")]
            for e in EMOJI_CHOICES
        ]
    )
    await message.answer("🙂 Выбери эмодзи-аватар:", reply_markup=kb)
    await state.set_state(OnboardingState.emoji)

# ═════ EMOJI ═════
@onboarding_router.callback_query(
    StateFilter(OnboardingState.emoji) & F.data.startswith("avatar:")
)
async def choose_avatar(cb: CallbackQuery, state: FSMContext):
    await state.update_data(avatar_emoji=cb.data.split(":", 1)[1])
    await cb.message.answer("📅 Когда ты бросил траву?", reply_markup=DATE_KB)
    await state.set_state(OnboardingState.choose_date)

# ═════ DATE ═════
@onboarding_router.callback_query(
    StateFilter(OnboardingState.choose_date) & (F.data == "set_date")
)
async def ask_date(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Введите дату (ДД.ММ.ГГГГ):")
    await state.set_state(OnboardingState.typing_date)

@onboarding_router.message(StateFilter(OnboardingState.typing_date))
async def save_date(message: Message, state: FSMContext):
    try:
        q_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        return await message.answer("❌ Формат неверный. Пример: 14.06.2024")
    await state.update_data(quit_date=q_date)
    await complete_registration(message.from_user.id, state, message.answer)

@onboarding_router.callback_query(
    StateFilter(OnboardingState.choose_date) & (F.data == "skip_date")
)
async def skip_date(cb: CallbackQuery, state: FSMContext):
    await state.update_data(quit_date=None)
    await complete_registration(cb.from_user.id, state, cb.message.answer)
    await cb.answer()
    await cb.message.delete()

# ═════ Finale ═════
async def complete_registration(telegram_id: int, state: FSMContext, reply_fn):
    data = await state.get_data()
    if {"pseudo", "avatar_emoji"} - data.keys():
        return await reply_fn("⚠️ Онбординг не завершён. /start")

    async with async_session() as ses:
        user: User | None = await ses.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )
        if user is None:            # ne devrait plus arriver
            user = User(telegram_id=telegram_id)
            ses.add(user)

        user.pseudo       = data["pseudo"]
        user.avatar_emoji = data["avatar_emoji"]
        user.quit_date    = data.get("quit_date")
        user.is_member    = user.is_member or user.lifetime_access  # garde cohérence
        await ses.commit()

    await reply_fn("✅ Профиль создан!")

    # Si accès lifetime → pas de bouton paiement
    async with async_session() as ses:
        user: User = await ses.scalar(
            select(User).where(User.telegram_id == telegram_id)
        )
        if user.lifetime_access:
            await reply_fn("🚀 Добро пожаловать в закрытый клуб!")
        else:
            await reply_fn("🚀 Готов вступить в закрытый клуб?", reply_markup=WELCOME_KB)

    await state.clear()

# ═════ DEMO ═════
@onboarding_router.callback_query(F.data == "demo")
async def show_demo(cb: CallbackQuery):
    demo = (
        "🆘 Пример /sos:\n"
        "«Ребята, жёстко тянет, помогите словами…»\n\n"
        "🏆 Пример /win:\n"
        "«30 дней без травы! Ощущаю энергию 💪»\n\n"
        "📊 /counter показывает личный стаж и статистику.\n"
    )
    await cb.message.answer(demo)
    await cb.answer()
