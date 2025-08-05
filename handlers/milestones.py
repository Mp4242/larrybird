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


def milestone_kb(msg_id: int, likes: int) -> InlineKeyboardMarkup:
    """
    Clavier sous chaque checkpoint :
      ├─ ✍️ Ответить
      └─ ❤️ / compteur de likes
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✍️ Ответить",
                callback_data=f"reply:{msg_id}"
            )],
            [InlineKeyboardButton(
                text=f"❤️ {likes}" if likes else "❤️",
                callback_data=f"like:{msg_id}"
            )]
        ]
    )


@milestone_router.callback_query(F.data.startswith("like:"))
async def like_milestone(cb: CallbackQuery):
    """
    Ajoute ou retire un like (1 like max par user & par message)
    """
    msg_id = int(cb.data.split(":", 1)[1])

    async with async_session() as ses:
        already = await ses.scalar(
            select(PostLike).where(
                PostLike.message_id == msg_id,
                PostLike.user_tg_id == cb.from_user.id)
        )

        if already:
            await ses.delete(already)                # on retire le like
        else:
            ses.add(PostLike(message_id=msg_id, user_tg_id=cb.from_user.id))

        likes = await ses.scalar(
            select(func.count()).select_from(
                PostLike).where(PostLike.message_id == msg_id)
        )
        await ses.commit()

    # MAJ du clavier
    await cb.message.edit_reply_markup(
        reply_markup=milestone_kb(msg_id, likes)
    )
    await cb.answer("👍")