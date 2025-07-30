import asyncio, logging
import random  # Ajout pour choice quotes
from datetime import date, timedelta  # Pour paid_until si monet

from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from sqlalchemy import select
import aiocron

from handlers import onboarding_router, main_router, counter_router, replies_router, posts_router, settings_router  # Ajoute posts/settings
from config import TOKEN, MILESTONES, SUPER_GROUP, TOPICS, TRIBUTE_WEBHOOK_SECRET  # Si webhook
from database.database import async_session
from database.user import User

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())
dp.include_router(onboarding_router)
dp.include_router(main_router)
dp.include_router(replies_router)
dp.include_router(counter_router)
dp.include_router(posts_router)  # Nouveau
dp.include_router(settings_router)  # Nouveau

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
                await bot.send_message(
                    SUPER_GROUP, TOPICS["wins"],
                    f"🥳 {u.avatar_emoji} <b>{u.pseudo}</b> празднует <b>{next_ms} д.</b>",
                    parse_mode="HTML"
                )
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

# Webhook Tribute (si monet, de précédent)
from aiohttp import web

async def handle_webhook(request):
    # ... comme précédent, russe messages si besoin ...
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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())