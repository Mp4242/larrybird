# from aiogram import Router, F
# from aiogram.types import CallbackQuery, Message
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.fsm.storage.base import StorageKey
# from aiogram.filters import StateFilter
# from aiogram.exceptions import TelegramForbiddenError
# from sqlalchemy import select
# import logging

# from config import SUPER_GROUP, BOT_USERNAME
# from database.database import async_session
# from database.user import User
# from database.post import Post
# from handlers.main import format_sobriety_duration, post_inline_keyboard

# replies_router = Router()
# logging.basicConfig(level=logging.INFO)

# # ───── FSM
# class ReplyState(StatesGroup):
#     waiting_for_text = State()


# # ───── Helpers
# async def profile_ok(user: User | None, reply_fn) -> bool:
#     if not user or not user.pseudo or not user.avatar_emoji:
#         await reply_fn("⚠️ Профиль не завершён. Напиши /start.")
#         return False
#     return True


# def link_to_post(msg_id: int) -> str:
#     return f"https://t.me/c/{str(SUPER_GROUP)[4:]}/{msg_id}"


# def deep_link(post_id: int) -> str:
#     return f"https://t.me/{BOT_USERNAME.lstrip('@')}?start=reply_{post_id}"


# # ───── Bouton « ✍️ Ответить » dans le groupe
# @replies_router.callback_query(F.data.startswith("reply:"))
# async def open_reply(cb: CallbackQuery, state: FSMContext):
#     post_id = int(cb.data.split(":", 1)[1])
#     logging.info(f"[CALLBACK] reply:{post_id} from {cb.from_user.id}")

#     async with async_session() as ses:
#         post = await ses.get(Post, post_id)
#         if not post:
#             return await cb.answer("❌ Пост не найден", show_alert=True)

#         user = await ses.scalar(select(User).where(User.telegram_id == cb.from_user.id))
#         if not await profile_ok(user, cb.message.answer):
#             return

#     # Popup dans le groupe
#     await cb.answer("✍️ Открой бот — там форма ответа.", show_alert=True)

#     # DM avec le lien vers le post
#     try:
#         await cb.message.bot.send_message(
#             cb.from_user.id,
#             f"📎 Ответ на <a href='{link_to_post(post_id)}'>пост #{post_id}</a>.\n\n"
#             f"✍️ Напиши свой ответ (до 500 симв.):",
#             parse_mode="HTML"
#         )
#     except TelegramForbiddenError:
#         return await cb.answer(
#             "❗ Нажми «Start» у бота, чтобы ответить",
#             url=deep_link(post_id),
#             show_alert=True
#         )

#     # ─── IMPORTANT : écrire la state dans le *scope privé* (chat_id = user_id)
#     private_key = StorageKey(
#         bot_id=cb.bot.id,
#         chat_id=cb.from_user.id,   # ✅ DM
#         user_id=cb.from_user.id
#     )
#     private_state = FSMContext(state.storage, key=private_key)

#     await private_state.set_state(ReplyState.waiting_for_text)
#     await private_state.update_data(reply_to=post_id)
#     logging.info(f"[FSM] waiting_for_text set for user {cb.from_user.id}")


# # ───── Annuler via commande
# @replies_router.message(StateFilter(ReplyState.waiting_for_text), F.text.startswith("/"))
# async def cancel_reply(msg: Message, state: FSMContext):
#     await state.clear()
#     await msg.answer("❌ Отменено.")


# # ───── Enregistrer la réponse
# @replies_router.message(StateFilter(ReplyState.waiting_for_text))
# async def save_reply(msg: Message, state: FSMContext):
#     logging.info("📥 save_reply triggered")

#     raw = (msg.text or "").strip()[:500]
#     if not raw:
#         return await msg.answer("❌ Текст пуст.")

#     data = await state.get_data()
#     post_id = data.get("reply_to")          # id du post d’origine

#     async with async_session() as ses:
#         post = await ses.get(Post, post_id)
#         if not post:
#             await msg.answer("⛔ Пост не найден.")
#             await state.clear()
#             return

#         user = await ses.scalar(select(User).where(User.telegram_id == msg.from_user.id))
#         if not await profile_ok(user, msg.answer):
#             return

#         # 1) Publier la réponse
#         reply_txt = (
#             f"📎 Ответ на <a href='{link_to_post(post.id)}'>пост #{post.id}</a>:\n\n"
#             f"{raw}\n\n"
#             f"—\n{user.avatar_emoji} {user.pseudo}  | {format_sobriety_duration(user.quit_date)}"
#         )
#         sent = await msg.bot.send_message(
#             chat_id=SUPER_GROUP,
#             message_thread_id=post.thread_id,
#             reply_to_message_id=post.id,
#             text=reply_txt,
#             parse_mode="HTML"
#         )
#         logging.info(f"✅ Reply sent ID {sent.message_id}")

#         # 2) Mettre à jour le post original
#         post.reply_count += 1
#         author = await ses.get(User, post.author_id)
#         updated_original = (
#             f"{post.text}\n\n"
#             f"—\n{author.avatar_emoji} {author.pseudo}  | "
#             f"{format_sobriety_duration(author.quit_date)}  | {post.reply_count} ответов"
#         )
#         await msg.bot.edit_message_text(
#             chat_id=SUPER_GROUP,
#             message_id=post.id,
#             text=updated_original,
#             reply_markup=post_inline_keyboard(author.id, post.id)
#         )

#         # 3) Persister la réponse
#         ses.add(Post(
#             id=sent.message_id,
#             author_id=user.id,
#             thread_id=post.thread_id,
#             text=raw
#         ))
#         await ses.commit()

#     await msg.answer("✅ Ответ опубликован!")
#     await state.clear()
#     logging.info(f"[FSM] cleared for user {msg.from_user.id}")


# # ───── Fallback DM hors FSM ────────────────────────────
# @replies_router.message(
#     F.chat.type == "private",
#     ~F.text.startswith("/"),
#     StateFilter(None)
# )
# async def fallback_dm(msg: Message):
#     await msg.answer("⚠️ Ты не в режиме ответа. Чтобы ответить на пост — нажми «✍️ Ответить» под ним.")



from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, LinkPreviewOptions
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from aiogram.filters import StateFilter
from aiogram.exceptions import TelegramForbiddenError
from sqlalchemy import select, func            
import logging

from config import SUPER_GROUP, BOT_USERNAME, TOPICS
from database.database import async_session
from database.user import User
from database.post import Post
from database.post_like import PostLike
from handlers.main import format_sobriety_duration, post_inline_keyboard

replies_router = Router()
logging.basicConfig(level=logging.INFO)

# ───── FSM
class ReplyState(StatesGroup):
    waiting_for_text = State()


# ───── Helpers
def link_to_post(msg_id: int) -> str:
    return f"https://t.me/c/{str(SUPER_GROUP)[4:]}/{msg_id}"


def deep_link(post_id: int) -> str:
    return f"https://t.me/{BOT_USERNAME.lstrip('@')}?start=reply_{post_id}"

async def warn_private(bot, tg_id: int, text: str):
    try:
        await bot.send_message(tg_id, text)
    except TelegramForbiddenError:
        pass   # on ne spamme pas le groupe

async def profile_ok(user: User | None, bot, tg_id: int) -> bool:
    if not user or not user.pseudo or not user.avatar_emoji:
        await warn_private(bot, tg_id, "⚠️ Сначала создай профиль → /start")
        return False
    return True

# ───── Bouton « ✍️ Ответить » dans le groupe
@replies_router.callback_query(F.data.startswith("reply:"))
async def open_reply(cb: CallbackQuery, state: FSMContext):
    post_id = int(cb.data.split(":", 1)[1])
    logging.info(f"[CALLBACK] reply:{post_id} from {cb.from_user.id}")

    async with async_session() as ses:
        post = await ses.get(Post, post_id)
        if not post:
            return await cb.answer("❌ Пост не найден", show_alert=True)

        user = await ses.scalar(select(User).where(User.telegram_id == cb.from_user.id))
        if not await profile_ok(user, cb.bot, cb.from_user.id):
            return

    # Popup dans le groupe
    await cb.answer("✍️ Открой бот — там форма ответа.", show_alert=True)

    # DM avec le lien vers le post
    try:
        await cb.message.bot.send_message(
            cb.from_user.id,
            f"📎 Ответ на <a href='{link_to_post(post_id)}'>пост #{post_id}</a>.\n\n"
            f"✍️ Напиши свой ответ (до 500 симв.):",
            parse_mode="HTML"
        )
    except TelegramForbiddenError:
        return await cb.answer(
            "❗ Нажми «Start» у бота, чтобы ответить",
            url=deep_link(post_id),
            show_alert=True
        )

    # ─── IMPORTANT : écrire la state dans le *scope privé* (chat_id = user_id)
    private_key = StorageKey(
        bot_id=cb.bot.id,
        chat_id=cb.from_user.id,   # ✅ DM
        user_id=cb.from_user.id
    )
    private_state = FSMContext(state.storage, key=private_key)

    await private_state.set_state(ReplyState.waiting_for_text)
    await private_state.update_data(reply_to=post_id)
    logging.info(f"[FSM] waiting_for_text set for user {cb.from_user.id}")


# ───── Annuler via commande
@replies_router.message(StateFilter(ReplyState.waiting_for_text), F.text.startswith("/"))
async def cancel_reply(msg: Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Отменено.")


# ───────────────────────  Enregistrer la réponse  ───────────────────────
@replies_router.message(StateFilter(ReplyState.waiting_for_text))
async def save_reply(msg: Message, state: FSMContext):
    logging.info("📥 save_reply triggered")

    raw = (msg.text or "").strip()[:500]
    if not raw:
        return await msg.answer("❌ Текст пуст.")

    data = await state.get_data()
    original_id: int | None = data.get("reply_to")     # id du post d’origine

    async with async_session() as ses:
        post = await ses.get(Post, original_id)
        if not post:
            await msg.answer("⛔ Пост не найден.")
            await state.clear()
            return

        user: User = await ses.scalar(select(User).where(User.telegram_id == msg.from_user.id))
        if not await profile_ok(user, msg.bot, msg.from_user.id):
            return

        # 1) Publier la réponse — lien vers le *post d’origine*, sans preview
        reply_txt = (
            f"<b>Ответ на пост</b> "
            f"<a href='{link_to_post(original_id)}'>#{original_id}</a>:\n\n"
            f"{raw}\n\n"
            f"—\n{user.avatar_emoji} {user.pseudo}  | "
            f"{format_sobriety_duration(user.quit_date)}"
        )
        sent = await msg.bot.send_message(
            chat_id=SUPER_GROUP,
            message_thread_id=post.thread_id,
            reply_to_message_id=original_id,
            text=reply_txt,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        logging.info(f"✅ Réponse publiée ID {sent.message_id}")

        # 2) Mettre à jour le post original
        post.reply_count += 1
        author = await ses.get(User, post.author_id)
        
        # libellé « N ответов »
        n = post.reply_count
        replies_label = f"✅ {n} ответ" if n == 1 else f"✅ {n} ответа" if 2 <= n <= 4 else f"✅ {n} ответов"

        updated = (
            f"{post.text}\n\n"
            f"—\n{author.avatar_emoji} {author.pseudo}  | "
            f"{format_sobriety_duration(author.quit_date)}  | {replies_label}"
        )

        # infos pour les boutons
        likes        = await ses.scalar(select(func.count()).select_from(PostLike).where(PostLike.post_id == original_id))
        with_support = post.thread_id == TOPICS["sos"]
        with_reply   = True      # toujours vrai pour un post-racine
        
        await msg.bot.edit_message_text(
            chat_id    = SUPER_GROUP,
            message_id = original_id,
            text       = updated,
            reply_markup = post_inline_keyboard(          # ❹ nouvel appel
                message_id   = original_id,
                with_reply   = with_reply,
                with_like    = True,
                with_support = with_support,
                likes        = likes
            )
        )

        # 3) Persister la réponse
        ses.add(Post(
            id=sent.message_id,
            author_id=user.id,
            thread_id=post.thread_id,
            parent_id=post.id,         # ← NEW  
            text=raw
        ))
        await ses.commit()

    await msg.answer("✅ Ответ опубликован!")
    await state.clear()
    logging.info(f"[FSM] cleared for {msg.from_user.id}")


# ───── Fallback DM hors FSM ────────────────────────────
@replies_router.message(
    F.chat.type == "private",
    ~F.text.startswith("/"),
    StateFilter(None)
)
async def fallback_dm(msg: Message):
    await msg.answer("⚠️ Ты не в режиме ответа. Чтобы ответить на пост — нажми «✍️ Ответить» под ним.")
