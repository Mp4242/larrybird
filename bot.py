import asyncio, logging
import random  # Ajout pour choice quotes
from datetime import date, timedelta  # Pour paid_until si monet

from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
import aiocron

from handlers import onboarding_router, main_router, counter_router, replies_router, posts_router, settings_router  # Ajoute posts/settings
from config import TOKEN, MILESTONES, SUPER_GROUP, TOPICS
from database.database import async_session
from database.user import User

from handlers.milestones import milestone_router, milestone_kb  
from sqlalchemy import select, func
from database.milestone_like import MilestoneLike            
from aiogram import F                                           

from handlers.pay import pay_router

from aiogram.types import BotCommand, BotCommandScopeDefault  # new import

from aiohttp import web

DEFAULT_COMMANDS = [
    BotCommand(command="start",    description="🚀 Главное меню"),
    BotCommand(command="sos",      description="🆘 Написать SOS"),
    BotCommand(command="win",      description="🏆 Поделиться WIN"),
    BotCommand(command="counter",  description="📊 Мой счётчик"),
    BotCommand(command="posts",    description="🗑 Мои сообщения"),
    BotCommand(command="settings", description="⚙️ Настройки"),
]

async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(DEFAULT_COMMANDS, BotCommandScopeDefault())

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())
dp.include_router(onboarding_router)
dp.include_router(main_router)
dp.include_router(replies_router)
dp.include_router(milestone_router)
dp.include_router(counter_router)
dp.include_router(posts_router)  # Nouveau
dp.include_router(settings_router)  # Nouveau
dp.include_router(pay_router)

QUOTES = [
    "Ты сильнее, чем думаешь! 💪",
    "Каждый день без травы - победа! 🏆",
    "Продолжай, ты на правильном пути! 🌟",
    # Добавьте больше в config.yml
]

# ─── CRON : checkpoints sobriety
@aiocron.crontab("30 0 * * *")
async def sobriety_check():
    async with async_session() as ses:
        users = (await ses.execute(select(User))).scalars().all()
        for u in users:
            if not u.quit_date:
                continue
            days = (date.today() - u.quit_date).days
            next_ms = next((m for m in MILESTONES if m > u.last_checkpoint), None)
            if next_ms and days >= next_ms:
                await bot.send_message(u.telegram_id,
                    f"🎉 Поздравляю! Сегодня {next_ms} дней без травы.")
                sent = await bot.send_message(
                    SUPER_GROUP, TOPICS["wins"],
                    f"🥳 {u.avatar_emoji} <b>{u.pseudo}</b> празднует <b>{next_ms} д.</b>",
                    parse_mode="HTML",
                    reply_markup=milestone_kb(0)  # placeholder
                )
                await sent.edit_reply_markup(milestone_kb(sent.message_id))
                u.last_checkpoint = next_ms
        await ses.commit()

# ─── CRON : motivation notifs (périodique par user)
@aiocron.crontab("0 9 * * *")  # Quotidien 9h, filtre par period
async def motivation_notifs():
    async with async_session() as ses:
        users = (await ses.execute(select(User).where(User.notifications_enabled == True))).scalars().all()
        for u in users:
            if u.quit_date and (date.today() - u.quit_date).days % u.notification_period == 0:
                quote = random.choice(QUOTES)
                await bot.send_message(u.telegram_id, quote)

async def handle_webhook(request):
    data = await request.json()
    if data.get("status") == "paid":
        uid = int(data["metadata"]["uid"])
        await bot.add_chat_member(SUPER_GROUP, uid)
        await bot.send_message(uid, "🎉 Добро пожаловать! Создай профиль → /start")
    return web.Response(status=200)

app = web.Application()
app.add_routes([web.post('/webhook', handle_webhook)])

async def start_webhook():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

async def main():
    asyncio.create_task(start_webhook())  # Optionnel si monet
    await set_bot_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())