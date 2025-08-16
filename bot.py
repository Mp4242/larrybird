# bot.py
from __future__ import annotations

import asyncio, logging, random
from datetime import date, datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiohttp import web
import aiocron
from sqlalchemy import select

from config import (
    TOKEN, MILESTONES, SUPER_GROUP, TOPICS,
    GRACE_DAYS, TRIBUTE_URL_TEMPLATE, ADMINS
)
from database.database import async_session
from database.user import User
from database.utils import get_user, create_user_stub, update_user

from aiogram import F

from handlers import (
    onboarding_router, main_router, counter_router,
    replies_router, posts_router, settings_router, debug_router
)
from handlers.pay import pay_router
from handlers.help import help_router
from handlers.main import post_inline_keyboard   # pour le clavier sous les posts

# ───────────────────────────  Bot / Dispatcher
logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp  = Dispatcher(storage=MemoryStorage())
for r in (
    onboarding_router, main_router, replies_router,
    counter_router, posts_router, settings_router, pay_router, help_router, debug_router,
):
    dp.include_router(r)

# ───────────────────────────  /commands
DEFAULT_COMMANDS = [
    BotCommand(command="start",    description="🚀 Главное меню"),
    BotCommand(command="sos",      description="🆘 Написать SOS"),
    BotCommand(command="win",      description="🏆 Поделиться WIN"),
    BotCommand(command="counter",  description="📊 Мой счётчик"),
    BotCommand(command="posts",    description="🗑 Мои сообщения"),
    BotCommand(command="settings", description="⚙️ Настройки"),
]
async def set_bot_commands(b: Bot):
    await b.set_my_commands(DEFAULT_COMMANDS, BotCommandScopeDefault())

# ───────────────────────────  Citations motivantes
QUOTES = [
    "Ты сильнее, чем думаешь! 💪",
    "Каждый день без травы — победа! 🏆",
    "Продолжай, ты на правильном пути! 🌟",
]

# ───────────────────────────  Cron : checkpoints sobriété (wins auto)
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
                # DM perso
                try:
                    await bot.send_message(
                        u.telegram_id,
                        f"🎉 Поздравляю! Сегодня {next_ms} дней трезвости."
                    )
                except Exception as e:
                    logging.warning("DM checkpoint failed %s: %s", u.telegram_id, e)

                # Post automatique dans WINS
                try:
                    sent = await bot.send_message(
                        SUPER_GROUP,
                        message_thread_id=TOPICS["wins"],
                        text=f"🥳 {u.avatar_emoji} <b>{u.pseudo}</b> празднует <b>{next_ms} дней трезвости.</b>",
                    )
                    await bot.edit_message_reply_markup(
                        SUPER_GROUP, sent.message_id,
                        reply_markup=post_inline_keyboard(
                            message_id=sent.message_id,
                            with_reply=True, with_like=True, with_support=False, likes=0
                        )
                    )
                except Exception as e:
                    logging.warning("Posting checkpoint failed for %s: %s", u.telegram_id, e)

                u.last_checkpoint = next_ms

        await ses.commit()

# ───────────────────────────  Cron : citations quotidiennes (9:00 UTC)
@aiocron.crontab("0 9 * * *")
async def motivation_notifs():
    async with async_session() as ses:
        users = (await ses.execute(
            select(User).where(User.notifications_enabled == True)
        )).scalars().all()

        for u in users:
            try:
                await bot.send_message(u.telegram_id, random.choice(QUOTES))
            except Exception as e:
                logging.debug("Motivation DM fail %s: %s", u.telegram_id, e)

# ───────────────────────────  Cron : expiration abonnements / essais (01:05 UTC)
@aiocron.crontab("5 1 * * *")
async def expire_memberships():
    now = datetime.utcnow()
    cutoff = now - timedelta(days=GRACE_DAYS)

    async with async_session() as ses:
        expired = (await ses.execute(
            select(User).where(
                User.is_member == True,
                User.paid_until.is_not(None),
                User.paid_until < cutoff
            )
        )).scalars().all()

        for u in expired:
            u.is_member = False
            # On enlève du groupe (ban+unban pour autoriser un retour via lien)
            try:
                await bot.ban_chat_member(SUPER_GROUP, u.telegram_id)
                await bot.unban_chat_member(SUPER_GROUP, u.telegram_id)
            except Exception as e:
                logging.warning("Remove from group failed %s: %s", u.telegram_id, e)

            # DM de renouvellement
            try:
                await bot.send_message(
                    u.telegram_id,
                    "⏳ Срок доступа истёк.\n"
                    "Чтобы вернуться в закрытый клуб, продли подписку:\n"
                    f"{TRIBUTE_URL_TEMPLATE}"
                )
            except Exception as e:
                logging.debug("DM renewal fail %s: %s", u.telegram_id, e)

        await ses.commit()

# ───────────────────────────  Webhook Tribute
async def handle_webhook(request: web.Request):
    data = await request.json()
    logging.warning("WEBHOOK DATA %s", data)

    event_name = (data.get("name") or "").strip()

    # Tribute envoie "new_subscription" (snake_case). Par prudence on accepte aussi camelCase.
    if event_name in {"new_subscription", "newSubscription"}:
        payload = data.get("payload") or {}
        try:
            uid = int(payload["telegram_user_id"])
        except Exception:
            logging.error("Webhook: telegram_user_id manquant ou invalide: %s", payload)
            return web.Response(text="bad request", status=400)

        # 1) paid_until = expires_at du webhook (ISO, termine par 'Z')
        raw_expires = payload.get("expires_at")
        until = None
        if raw_expires:
            try:
                # "2025-04-20T01:15:57.305733Z" -> datetime UTC
                until = datetime.fromisoformat(raw_expires.replace("Z", "+00:00"))
            except Exception as e:
                logging.warning("Parse expires_at échoué (%s): %s", raw_expires, e)

        # Fallback si jamais expires_at absent ou invalide
        if until is None:
            until = datetime.utcnow() + timedelta(days=31)

        # 2) Upsert user + statut membre
        user = await get_user(uid)
        if user:
            await update_user(uid, is_member=True, paid_until=until)
        else:
            await create_user_stub(uid)
            await update_user(uid, is_member=True, paid_until=until)

        # 3) Lien d’invitation one-shot (utile si pas encore dans le groupe)
        try:
            invite = await bot.create_chat_invite_link(SUPER_GROUP, member_limit=1)
            await bot.send_message(
                uid,
                f"🎉 Оплата принята!\n"
                f"Доступ активен до <b>{until.strftime('%d.%m.%Y')}</b>.\n"
                f"➡️ Вступай: {invite.invite_link}"
            )
        except Exception as e:
            logging.warning("Invite link fail for %s: %s", uid, e)

        return web.Response(text="ok")

    # (Facultatif) autres events ignorés proprement
    return web.Response(text="ignored")


# =================================================================
# 1) JOBS TESTABLES (appelables à la main ET par le cron)
# =================================================================

async def sobriety_check_job():
    async with async_session() as ses:
        users = (await ses.execute(select(User))).scalars().all()
        for u in users:
            if not u.quit_date:
                continue
            days    = (date.today() - u.quit_date).days
            next_ms = next((m for m in MILESTONES if m > u.last_checkpoint), None)
            if next_ms and days >= next_ms:
                # DM
                try:
                    await bot.send_message(u.telegram_id, f"🎉 Поздравляю! Сегодня {next_ms} дней трезвости.")
                except Exception as e:
                    logging.warning("DM checkpoint failed %s: %s", u.telegram_id, e)
                # Post auto dans WINS
                try:
                    sent = await bot.send_message(
                        SUPER_GROUP,
                        message_thread_id=TOPICS["wins"],
                        text=f"🥳 {u.avatar_emoji} <b>{u.pseudo}</b> празднует <b>{next_ms} дней трезвости.</b>",
                    )
                    await bot.edit_message_reply_markup(
                        SUPER_GROUP, sent.message_id,
                        reply_markup=post_inline_keyboard(
                            message_id=sent.message_id,
                            with_reply=True, with_like=True, with_support=False, likes=0
                        )
                    )
                except Exception as e:
                    logging.warning("Posting checkpoint failed for %s: %s", u.telegram_id, e)
                u.last_checkpoint = next_ms
        await ses.commit()


async def motivation_notifs_job():
    async with async_session() as ses:
        users = (await ses.execute(
            select(User).where(User.notifications_enabled == True)
        )).scalars().all()

        for u in users:
            try:
                await bot.send_message(u.telegram_id, random.choice(QUOTES))
            except Exception as e:
                logging.debug("Motivation DM fail %s: %s", u.telegram_id, e)


async def expire_memberships_job():
    now = datetime.utcnow()
    cutoff = now - timedelta(days=GRACE_DAYS)
    async with async_session() as ses:
        expired = (await ses.execute(
            select(User).where(
                User.is_member == True,
                User.paid_until.is_not(None),
                User.paid_until < cutoff
            )
        )).scalars().all()

        for u in expired:
            u.is_member = False
            try:
                await bot.ban_chat_member(SUPER_GROUP, u.telegram_id)
                await bot.unban_chat_member(SUPER_GROUP, u.telegram_id)
            except Exception as e:
                logging.warning("Remove from group failed %s: %s", u.telegram_id, e)
            try:
                await bot.send_message(
                    u.telegram_id,
                    "⏳ Срок доступа истёк.\n"
                    "Чтобы вернуться в закрытый клуб, продли подписку:\n"
                    f"{TRIBUTE_URL_TEMPLATE}"
                )
            except Exception as e:
                logging.debug("DM renewal fail %s: %s", u.telegram_id, e)
        await ses.commit()

# =================================================================
# 2) PLANNING CRON (les réveils quotidiens) — NE PAS APPELER DIRECTEMENT
# =================================================================

@aiocron.crontab("30 0 * * *")
async def sobriety_check():
    await sobriety_check_job()

@aiocron.crontab("0 9 * * *")
async def motivation_notifs():
    await motivation_notifs_job()

@aiocron.crontab("5 1 * * *")
async def expire_memberships():
    await expire_memberships_job()

# =================================================================
# 3) COMMANDES ADMIN POUR TESTER À LA DEMANDE
# =================================================================

@dp.message(F.text == "/cron_checkpoints")
async def _cron_checkpoints(msg):
    if msg.from_user.id not in ADMINS:
        return
    await sobriety_check_job()
    await msg.answer("✅ Checkpoints exécutés (manuel).")

@dp.message(F.text == "/cron_motivation")
async def _cron_motivation(msg):
    if msg.from_user.id not in ADMINS:
        return
    await motivation_notifs_job()
    await msg.answer("✅ Motivations envoyées (manuel).")

@dp.message(F.text == "/cron_expire")
async def _cron_expire(msg):
    if msg.from_user.id not in ADMINS:
        return
    await expire_memberships_job()
    await msg.answer("✅ Expirations traitées (manuel).")


# ───────────────────────────  aiohttp
app = web.Application()
app.add_routes([web.post("/webhook", handle_webhook)])

async def start_webhook():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

# ───────────────────────────  Main
async def main():
    asyncio.create_task(start_webhook())
    await set_bot_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
