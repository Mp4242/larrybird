# handlers/milestones.py
"""Обработчики и утилиты для сообщений-вех (milestones) :
    • Функция `milestone_kb()` строит inline-клавиатуру с кнопкой ответа и лайка
    • Callback-handler `like_milestone()` инкрементирует лайки (один лайк на пользователя)
Подключить router в bot.py :
    from handlers.milestones import milestone_router
    dp.include_router(milestone_router)
"""

from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, select

from database.database import async_session
from database.milestone_like import MilestoneLike

milestone_router = Router()


def milestone_kb(msg_id: int, likes: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура для поста-вехи.
    :param msg_id: ID сообщения в группе (нужен для callback).
    :param likes:  Текущее число лайков.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("✍️ Ответить", callback_data=f"reply:{msg_id}")],
            [InlineKeyboardButton(f"👍 {likes}",   callback_data=f"like:{msg_id}")],
        ]
    )


@milestone_router.callback_query(F.data.startswith("like:"))
async def like_milestone(cb: CallbackQuery):
    """Добавляет лайк к milestone-сообщению. Уникальное ограничение UX исключает повторный лайк."""
    msg_id = int(cb.data.split(":")[1])

    async with async_session() as ses:
        try:
            # Пытаемся записать лайк. Если уже есть – ловим IntegrityError.
            ses.add(MilestoneLike(message_id=msg_id, user_id=cb.from_user.id))
            await ses.commit()
        except IntegrityError:
            await cb.answer("Уже лайкнул 🙂", show_alert=True)
            return

        likes = await ses.scalar(
            select(func.count()).select_from(MilestoneLike).where(MilestoneLike.message_id == msg_id)
        )

    # Обновляем счётчик на кнопке
    await cb.message.edit_reply_markup(milestone_kb(msg_id, likes))
    await cb.answer("👍")