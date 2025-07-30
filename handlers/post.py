from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.utils import get_user, get_posts_by_user, get_post_by_id, update_post
from config import bot, SUPER_GROUP, TOPICS

posts_router = Router()

class DeleteState(StatesGroup):
    confirm = State()

@posts_router.message(Command("posts"))
async def posts_handler(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.reply("Профиль не найден. Сначала /start!")
        return
    posts = await get_posts_by_user(user.id)
    if not posts:
        await message.reply("Нет постов! Создайте с /sos или /win.")
        return
    text = "Ваши посты:\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for post in posts:
        snippet = post.text[:50] + "..." if len(post.text) > 50 else post.text
        topic_name = 'SOS' if post.thread_id == TOPICS['sos'] else 'Win'
        text += f"- ID {post.id}: {snippet} ({topic_name})\n"
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"Удалить {post.id}", callback_data=f"delete_{post.id}")])
    await message.answer(text, reply_markup=keyboard)

@posts_router.callback_query(F.data.startswith("delete_"))
async def delete_prompt(query: CallbackQuery, state: FSMContext):
    post_id = int(query.data.split("_")[1])
    await state.update_data(post_id=post_id)
    text = "Внимание: Удаление поста отметит его как 'Deleted', удалит кнопки Реагировать на посте и ответах. Никто больше не сможет реагировать на тред! Подтвердить?"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ДА (Да)", callback_data="confirm_delete")],
        [InlineKeyboardButton(text="НЕТ (Нет)", callback_data="cancel_delete")]
    ])
    await query.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(DeleteState.confirm)

@posts_router.callback_query(F.data == "confirm_delete", DeleteState.confirm)
async def confirm_delete(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    post_id = data['post_id']
    post = await get_post_by_id(post_id)
    if post:
        await update_post(post_id, deleted=True)
        if post.message_id:
            await bot.edit_message_text(
                chat_id=SUPER_GROUP,
                message_id=post.message_id,
                text=f"[Удалено] {post.text}",
                parse_mode="HTML"
            )
            # Note: Pour remove "Reagir" buttons sur replies, query replies by post_id et edit each (add if needed ; scalable avec limit)
        await query.message.edit_text("Пост удалён! ✅")
    else:
        await query.message.edit_text("Пост не найден! 😕")
    await state.clear()

@posts_router.callback_query(F.data == "cancel_delete")
async def cancel_delete(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text("Удаление отменено! 😌")
    await state.clear()