"""
Middleware для проверки подписки на канал и бана пользователей.
"""

from typing import Callable, Dict, Any, Awaitable
import logging
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import CHANNEL_ID, CHANNEL_URL, ADMIN_ID

logger = logging.getLogger(__name__)


class SubscriptionCheckMiddleware(BaseMiddleware):
    """Проверяет бан и подписку пользователя на канал перед обработкой запроса."""

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # Пропускаем админа
        if event.from_user.id == ADMIN_ID:
            logger.debug(f"[Middleware] Пропускаем админа {event.from_user.id}")
            return await handler(event, data)

        # Проверяем бан пользователя
        from database.db import async_session
        from database.models import User
        from sqlalchemy import select

        async with async_session() as session:
            result = await session.execute(select(User).where(User.id == event.from_user.id))
            user = result.scalar_one_or_none()

            if user and user.is_banned:
                logger.info(f"[Middleware] Пользователь {event.from_user.id} забанен")

                # Разрешаем только команду /help и callback support
                is_help_command = isinstance(event, Message) and event.text and event.text.startswith('/help')
                is_support_callback = isinstance(event, CallbackQuery) and event.data == "support"

                if not (is_help_command or is_support_callback):
                    text = (
                        "🚫 <b>Доступ ограничен</b>\n\n"
                        "Ваш аккаунт заблокирован администрацией.\n\n"
                        "Для уточнения причин свяжитесь с поддержкой:\n"
                        "📧 Email: sakuravpnsupp@gmail.com\n"
                        "💬 Telegram: @sakuravpn_supp"
                    )

                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💬 Поддержка", callback_data="support")]
                    ])

                    try:
                        if isinstance(event, Message):
                            await event.answer(text, parse_mode="HTML", reply_markup=keyboard)
                        elif isinstance(event, CallbackQuery):
                            await event.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
                            await event.answer("Ваш аккаунт заблокирован", show_alert=True)
                    except Exception as e:
                        logger.error(f"[Middleware] Ошибка отправки сообщения о бане: {e}")

                    return  # Прерываем обработку

        # Если канал не настроен, пропускаем проверку подписки
        if not CHANNEL_ID:
            logger.debug("[Middleware] CHANNEL_ID не настроен, пропускаем проверку")
            return await handler(event, data)

        # Пропускаем команду /start для новых пользователей
        if isinstance(event, Message) and event.text and event.text.startswith('/start'):
            logger.debug(f"[Middleware] Пропускаем команду /start для user_id={event.from_user.id}")
            return await handler(event, data)

        # Пропускаем callback проверки подписки (иначе цикл)
        if isinstance(event, CallbackQuery) and event.data == "check_subscription":
            logger.debug(f"[Middleware] Пропускаем callback check_subscription для user_id={event.from_user.id}")
            return await handler(event, data)

        # Проверяем подписку
        try:
            member = await event.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=event.from_user.id)
            # Статусы: creator, administrator, member - подписан
            # left, kicked - не подписан
            if member.status in ["creator", "administrator", "member"]:
                logger.debug(f"[Middleware] Пользователь {event.from_user.id} подписан на канал (статус: {member.status})")
                return await handler(event, data)
            else:
                logger.info(f"[Middleware] Пользователь {event.from_user.id} НЕ подписан на канал (статус: {member.status})")
        except Exception as e:
            logger.error(f"[Middleware] Ошибка проверки подписки для user_id={event.from_user.id}: {e}")
            # В случае ошибки пропускаем (например, бот не админ в канале)
            return await handler(event, data)

        # Пользователь не подписан - показываем сообщение
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL or "https://t.me/your_channel")],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")]
        ])

        text = (
            "🔒 <b>Доступ ограничен</b>\n\n"
            "Для использования бота необходимо подписаться на наш канал.\n\n"
            "После подписки нажми «Я подписался»"
        )

        try:
            if isinstance(event, Message):
                await event.answer(text, parse_mode="HTML", reply_markup=keyboard)
                logger.info(f"[Middleware] Отправлено сообщение о подписке user_id={event.from_user.id}")
            elif isinstance(event, CallbackQuery):
                await event.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
                await event.answer("Подпишись на канал для продолжения", show_alert=True)
                logger.info(f"[Middleware] Отправлен callback о подписке user_id={event.from_user.id}")
        except Exception as e:
            logger.error(f"[Middleware] Ошибка отправки сообщения о подписке: {e}")

        return  # Прерываем обработку
