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

from database.utils import get_user

onboarding_router = Router()

# ─── FSM ────────────────────────────────────────────────
class OnboardingState(StatesGroup):
    pseudo       = State()
    emoji        = State()
    choose_date  = State()
    typing_date  = State()

# ─── UI constantes ─────────────────────────────────────
EMOJI_CHOICES = ["😎", "👤", "🦁", "🐺", "🦅", "🐯", "🔥", "💪", "🥷", "👽"]
PSEUDO_RE     = re.compile(r"^(?!/)\S{1,30}$", re.UNICODE)

DATE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🗓️ Указать дату", callback_data="set_date")],
        [InlineKeyboardButton(text="⏭️ Укажу позже",  callback_data="skip_date")]
    ]
)

# ─── clavier accueil (avant cmd_start) ───
WELCOME_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💳 Вступить за 149 ₽", callback_data="pay")],
        [InlineKeyboardButton(text="👀 Посмотреть демо",    callback_data="demo")],
    ]
)

# ─────────────────────────────────────────────────────── /start
@onboarding_router.message(F.text == "/start")
async def cmd_start(msg: Message, state: FSMContext):
    user = await get_user(msg.from_user.id)

    # ① pas encore payé → propose pay/demo
    if not user:
        await msg.answer(
            "🔥 Приватный клуб отказа от травы.\n"
            "Посмотри демо или вступай со скидкой 70 % 👇",
            reply_markup=WELCOME_KB,
        )
        return

    # ② payé mais profil не заполнен
    if not user.pseudo:
        await msg.answer("✏️ Введи псевдоним (1–30 символов):")
        await state.set_state(OnboardingState.pseudo)
        return

    # ③ уже в клубе
    await msg.answer("👋 Ты уже в клубе. /help — команды.")


# ────────────────────────────────────────────────── PSEUDO
@onboarding_router.message(StateFilter(OnboardingState.pseudo))
async def set_pseudo(message: Message, state: FSMContext):
    raw = message.text.strip()
    if not PSEUDO_RE.match(raw):
        return await message.answer("❌ 1-30 символов, без пробелов. Попробуй ещё:")
    await state.update_data(pseudo=raw)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=e, callback_data=f"avatar:{e}")]
                         for e in EMOJI_CHOICES]
    )
    await message.answer("🙂 Выбери эмодзи-аватар:", reply_markup=kb)
    await state.set_state(OnboardingState.emoji)

# ────────────────────────────────────────────────── EMOJI
@onboarding_router.callback_query(StateFilter(OnboardingState.emoji), F.data.startswith("avatar:"))
async def choose_avatar(cb: CallbackQuery, state: FSMContext):
    await state.update_data(avatar_emoji=cb.data.split(":", 1)[1])
    await cb.message.answer("📅 Когда ты бросил траву?", reply_markup=DATE_KB)
    await state.set_state(OnboardingState.choose_date)

# ──────────────────────────────────────── DATE : demander
@onboarding_router.callback_query(StateFilter(OnboardingState.choose_date), F.data == "set_date")
async def ask_date(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Введите дату (ДД.ММ.ГГГГ):")
    await state.set_state(OnboardingState.typing_date)

# ──────────────────────────────────────── DATE : sauver
@onboarding_router.message(StateFilter(OnboardingState.typing_date))
async def save_date(message: Message, state: FSMContext):
    try:
        q_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        return await message.answer("❌ Формат неверный. Пример: 14.06.2024")
    await state.update_data(quit_date=q_date)
    await complete_registration(message.from_user.id, state, message.answer)

# ──────────────────────────────────────── DATE : skip
@onboarding_router.callback_query(StateFilter(OnboardingState.choose_date), F.data == "skip_date")
async def skip_date(cb: CallbackQuery, state: FSMContext):
    await state.update_data(quit_date=None)
    await complete_registration(cb.from_user.id, state, cb.message.answer)
    await cb.answer()
    await cb.message.delete()

# ─────────────────────────────── Финал регистрации
async def complete_registration(telegram_id: int, state: FSMContext, reply_fn):
    data = await state.get_data()
    if "pseudo" not in data or "avatar_emoji" not in data:
        return await reply_fn("⚠️ Онбординг не завершён. /start")

    async with async_session() as ses:
        ses.add(User(
            telegram_id=telegram_id,
            pseudo=data["pseudo"],
            avatar_emoji=data["avatar_emoji"],
            quit_date=data.get("quit_date")
        ))
        await ses.commit()

    await reply_fn("✅ Профиль создан!")

    # ——— Boutons DEMO & Payer ———
    pay_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 -80 % первый месяц", callback_data="pay")],
            [InlineKeyboardButton(text="👀 Демо",               callback_data="demo")],
        ]
    )
    await reply_fn("🚀 Готов вступить в закрытый клуб?", reply_markup=pay_kb)
    await state.clear()

# ─────────────────────────────── DEMO (aperçu gratuit)
@onboarding_router.callback_query(F.data == "demo")
async def show_demo(cb: CallbackQuery):
    demo = (
        "🆘 Пример /sos:\n"
        "«Ребята, жестко тянет, помогите словами…»\n\n"
        "🏆 Пример /win:\n"
        "«30 дней без травы! Ощущаю энергию 💪»\n\n"
        "📊 /counter показывает личный стаж и статистику.\n"
    )
    await cb.message.answer(demo)
    await cb.answer()
