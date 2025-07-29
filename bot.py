import asyncio, logging
from datetime import date

from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from sqlalchemy import select
import aiocron

from handlers import onboarding_router, main_router, counter_router
from handlers.replies import replies_router       # après correctif
from config  import TOKEN, MILESTONES, SUPER_GROUP, TOPICS
from database.database import async_session
from database.user      import User

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())          # ← aucun fsm_strategy spécial
dp.include_router(onboarding_router)
dp.include_router(main_router)
dp.include_router(replies_router)
dp.include_router(counter_router)

# ─── CRON : checkpoints
@aiocron.crontab("30 0 * * *")
async def sobriety_check():
    async with async_session() as ses:
        users = (await ses.execute(select(User))).scalars().all()
        for u in users:
            if not u.quit_date:
                continue
            days     = (date.today() - u.quit_date).days
            next_ms  = next((m for m in MILESTONES if m > u.last_checkpoint), None)
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

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
