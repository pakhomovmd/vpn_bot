"""
Планировщик фоновых задач (APScheduler).

Задачи:
- Каждый день проверяем истекающие подписки и уведомляем юзеров
- Деактивируем истёкшие подписки в 3X-UI
"""

from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from database.db import async_session
from database.models import Subscription, User
from services.vpn import xray

scheduler = AsyncIOScheduler()


async def check_expiring_subscriptions(bot):
    """
    Запускается каждый день в 10:00.
    Уведомляет пользователей у кого подписка истекает через 3 дня или завтра.
    """
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.is_active == True,
                Subscription.expires_at > now,
                Subscription.expires_at <= now + timedelta(days=3)
            )
        )
        subs = result.scalars().all()

        for sub in subs:
            days_left = (sub.expires_at - now).days
            if days_left <= 0:
                continue
            try:
                await bot.send_message(
                    sub.user_id,
                    f"⚠️ <b>Подписка заканчивается через {days_left} дн.</b>\n\n"
                    f"Продли подписку, чтобы не потерять доступ к VPN.",
                    parse_mode="HTML"
                )
                print(f"[Scheduler] Уведомление отправлено user_id={sub.user_id}, осталось {days_left} дн.")
            except Exception as e:
                print(f"[Scheduler] Не удалось уведомить user_id={sub.user_id}: {e}")


async def deactivate_expired_subscriptions():
    """
    Запускается каждый час.
    Деактивирует истёкшие подписки в базе и в 3X-UI.
    """
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.is_active == True,
                Subscription.expires_at <= now
            )
        )
        subs = result.scalars().all()

        for sub in subs:
            print(f"[Scheduler] Деактивируем подписку user_id={sub.user_id}, uuid={sub.xray_uuid}")
            sub.is_active = False
            
            # Отключаем VPN клиента в 3X-UI
            success = await xray.disable_client(sub.xray_uuid)
            if success:
                print(f"[Scheduler] VPN клиент {sub.xray_uuid} успешно отключен")
            else:
                print(f"[Scheduler] Не удалось отключить VPN клиента {sub.xray_uuid}")

        await session.commit()
        if subs:
            print(f"[Scheduler] Деактивировано {len(subs)} истёкших подписок")
        else:
            print(f"[Scheduler] Истёкших подписок не найдено")


def setup_scheduler(bot):
    """Регистрируем задачи и запускаем планировщик."""
    scheduler.add_job(
        check_expiring_subscriptions,
        trigger="cron",
        hour=10, minute=0,
        args=[bot]
    )
    scheduler.add_job(
        deactivate_expired_subscriptions,
        trigger="interval",
        hours=1
    )
    scheduler.start()
    print("[Scheduler] Запущен")
