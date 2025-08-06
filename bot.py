# bot.py — version corrigée (BotCommand kwargs)
import asyncio, logging, random
from datetime import date
from datetime import datetime, timedelta 

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiohttp import web
import aiocron
from sqlalchemy import select, func

from config import TOKEN, MILESTONES, SUPER_GROUP, TOPICS
from database.database import async_session
from database.user import User
from database.utils import get_user, create_user_stub, update_user

from handlers import (
    onboarding_router, main_router, counter_router, replies_router,
    posts_router, settings_router
)
from handlers.milestones import milestone_router, milestone_kb
from handlers.pay import pay_router
from handlers.help import help_router   # import

# ──────────────────────────── Bot & Dispatcher
logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher(storage=MemoryStorage())
for r in (
    onboarding_router, main_router, replies_router, milestone_router,
    counter_router, posts_router, settings_router, pay_router, help_router,
):
    dp.include_router(r)

# ──────────────────────────── Commands (kwargs)
DEFAULT_COMMANDS = [
    BotCommand(command="start",    description="🚀 Главное меню"),
    BotCommand(command="sos",      description="🆘 Написать SOS"),
    BotCommand(command="win",      description="🏆 Поделиться WIN"),
    BotCommand(command="counter",  description="📊 Мой счётчик"),
    BotCommand(command="posts",    description="🗑 Мои сообщения"),
    BotCommand(command="settings", description="⚙️ Настройки"),
]

async def set_bot_commands(bot_: Bot):
    await bot_.set_my_commands(DEFAULT_COMMANDS, BotCommandScopeDefault())

# ──────────────────────────── Quotes
QUOTES = [
    "Ты сильнее, чем думаешь! 💪",
    "Каждый день без травы - победа! 🏆",
    "Продолжай, ты на правильном пути! 🌟",
]

# ──────────────────────────── Sobriety checkpoints (cron)
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
                await bot.send_message(u.telegram_id, f"🎉 Поздравляю! Сегодня {next_ms} дней без травы.")
                sent = await bot.send_message(
                    SUPER_GROUP,
                    TOPICS["wins"],
                    f"🥳 {u.avatar_emoji} <b>{u.pseudo}</b> празднует <b>{next_ms} д.</b>",
                    parse_mode="HTML",
                    reply_markup=milestone_kb(0),
                )
                await sent.edit_reply_markup(milestone_kb(sent.message_id))
                u.last_checkpoint = next_ms
        await ses.commit()

# ──────────────────────────── Motivation quotes (cron)
@aiocron.crontab("0 9 * * *")
async def motivation_notifs():
    async with async_session() as ses:
        users = (
            await ses.execute(select(User).where(User.notifications_enabled == True))
        ).scalars().all()
        for u in users:
            if u.quit_date and (date.today() - u.quit_date).days % u.notification_period == 0:
                await bot.send_message(u.telegram_id, random.choice(QUOTES))

# ──────────────────────────── Webhook Tribute
async def handle_webhook(request: web.Request):
    data = await request.json()
    logging.warning("WEBHOOK DATA %s", data)

    if data.get("name") == "new_subscription":          # Tribute v2
        uid = int(data["payload"]["telegram_user_id"])

        # ▸ 1. marquer « membre » (paid_until = +31 jours pour l’exemple)
        until = datetime.utcnow() + timedelta(days=31)
        user = await get_user(uid)
        if user:
            await update_user(uid, is_member=True, paid_until=until)
        else:
            await create_user_stub(uid)
            # Quoi qu’il arrive, on confirme l’abonnement
            until = (datetime.utcnow() + timedelta(days=31)).date()
            await update_user(uid, is_member=True, paid_until=until)

        # ▸ 2. inviter dans le groupe privé
        try:
            await bot.invite_chat_member(SUPER_GROUP, uid)
        except Exception:
            pass                                         # déjà invité ?

        # ▸ 3. DM de confirmation
        await bot.send_message(
            uid,
            "🎉 Платёж прошёл! Теперь создай профиль → /start"
            "\n(Если уже создавал — просто используй команды)"
        )

    return web.Response(text="ok")

# ──────────────────────────── aiohttp app
app = web.Application()
app.add_routes([web.post("/webhook", handle_webhook)])

async def start_webhook():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

# ──────────────────────────── Main
async def main():
    asyncio.create_task(start_webhook())
    await set_bot_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
