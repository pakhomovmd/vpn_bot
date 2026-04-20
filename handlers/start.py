"""
Хэндлер /start — регистрация, триал, реферальная система.
"""

import random
import string
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import TRIAL_DAYS, REFERRAL_BONUS_DAYS, ADMIN_ID
from database.models import User, Subscription, ReferralBonus
from database.db import async_session
from keyboards.inline import main_menu, back_main
from services.vpn import xray

router = Router()


def generate_referral_code(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


async def get_or_create_user(tg_user, bot: Bot, referral_code: str | None = None) -> tuple[User, bool]:
    """
    Возвращает (user, is_new).
    is_new = True если пользователь только что зарегистрирован.
    """
    async with async_session() as session:
        # Проверяем есть ли уже такой пользователь
        result = await session.execute(select(User).where(User.id == tg_user.id))
        user = result.scalar_one_or_none()
        if user:
            return user, False

        # Ищем реферера по коду
        referrer = None
        if referral_code:
            ref_result = await session.execute(
                select(User).where(User.referral_code == referral_code)
            )
            referrer = ref_result.scalar_one_or_none()
            # Не принимаем собственный код
            if referrer and referrer.id == tg_user.id:
                referrer = None

        # Создаём пользователя
        new_user = User(
            id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
            referral_code=generate_referral_code(),
            referred_by=referrer.id if referrer else None,
            is_admin=(tg_user.id == ADMIN_ID),
        )
        session.add(new_user)
        await session.flush()

        # Выдаём триал VPN
        print(f"[Start] Создаём VPN клиента для user_id={tg_user.id}, days={TRIAL_DAYS}")
        vpn_client = await xray.create_client(tg_user.id, TRIAL_DAYS)

        if vpn_client:
            print(f"[Start] VPN клиент создан: {vpn_client['uuid']}")
            sub = Subscription(
                user_id=new_user.id,
                xray_uuid=vpn_client["uuid"],
                vless_link=vpn_client["vless_link"],
                plan_key="trial",
                expires_at=datetime.now() + timedelta(days=TRIAL_DAYS),
            )
            session.add(sub)
            new_user.trial_used = True
        else:
            print(f"[Start] ОШИБКА: не удалось создать VPN клиента для {tg_user.id}")

        # Реферальный бонус
        if referrer:
            print(f"[Start] Начисляем реферальный бонус: referrer_id={referrer.id}, referred_id={new_user.id}")
            
            # Проверяем не получал ли реферер уже бонус за этого пользователя
            existing_bonus_result = await session.execute(
                select(ReferralBonus).where(
                    ReferralBonus.referrer_id == referrer.id,
                    ReferralBonus.referred_id == new_user.id
                )
            )
            existing_bonus = existing_bonus_result.scalar_one_or_none()
            
            if existing_bonus:
                print(f"[Start] Бонус уже был начислен ранее, пропускаем")
            else:
                bonus = ReferralBonus(
                    referrer_id=referrer.id,
                    referred_id=new_user.id,
                    bonus_days=REFERRAL_BONUS_DAYS,
                )
                session.add(bonus)

                # Продлеваем подписку реферера
                ref_sub_result = await session.execute(
                    select(Subscription)
                    .where(Subscription.user_id == referrer.id, Subscription.is_active == True)
                    .order_by(Subscription.expires_at.desc())
                )
                ref_sub = ref_sub_result.scalar_one_or_none()
                
                if ref_sub:
                    print(f"[Start] Продлеваем подписку реферера: uuid={ref_sub.xray_uuid}, days={REFERRAL_BONUS_DAYS}")
                    old_expires = ref_sub.expires_at
                    ref_sub.expires_at += timedelta(days=REFERRAL_BONUS_DAYS)
                    
                    # Продлеваем в 3X-UI
                    extend_success = await xray.extend_client(ref_sub.xray_uuid, REFERRAL_BONUS_DAYS)
                    if extend_success:
                        print(f"[Start] Подписка реферера успешно продлена в 3X-UI")
                    else:
                        print(f"[Start] ОШИБКА: не удалось продлить подписку в 3X-UI")
                    
                    # Уведомляем реферера
                    try:
                        from datetime import timezone as tz
                        time_left = ref_sub.expires_at - datetime.now(tz.utc)
                        days_left = time_left.days
                        hours_left = (time_left.seconds // 3600)
                        
                        time_str = f"{days_left} дн. {hours_left} ч." if hours_left > 0 else f"{days_left} дн."
                        
                        await bot.send_message(
                            referrer.id,
                            f"🎉 По твоей реферальной ссылке зарегистрировался новый пользователь!\n\n"
                            f"✅ Тебе начислено <b>+{REFERRAL_BONUS_DAYS} дня</b> к подписке.\n"
                            f"⏳ Подписка теперь активна ещё <b>{time_str}</b>",
                            parse_mode="HTML"
                        )
                        print(f"[Start] Уведомление реферера {referrer.id} отправлено")
                    except Exception as e:
                        print(f"[Start] Не удалось уведомить реферера {referrer.id}: {e}")
                else:
                    print(f"[Start] У реферера {referrer.id} нет активной подписки для продления")
                    # Всё равно уведомляем о регистрации
                    try:
                        await bot.send_message(
                            referrer.id,
                            f"🎉 По твоей реферальной ссылке зарегистрировался новый пользователь!\n\n"
                            f"✅ Тебе начислено <b>+{REFERRAL_BONUS_DAYS} дня</b> бонуса.\n"
                            f"💡 Купи подписку, чтобы использовать бонусные дни!",
                            parse_mode="HTML"
                        )
                        print(f"[Start] Уведомление реферера {referrer.id} (без подписки) отправлено")
                    except Exception as e:
                        print(f"[Start] Не удалось уведомить реферера {referrer.id}: {e}")

        await session.commit()
        await session.refresh(new_user)
        return new_user, True


@router.message(CommandStart())
async def cmd_start(message: Message):
    args = message.text.split()
    referral_code = args[1] if len(args) > 1 else None

    async with async_session() as session:
        # Проверяем пользователя
        result = await session.execute(select(User).where(User.id == message.from_user.id))
        user = result.scalar_one_or_none()
        
        if not user:
            # Новый пользователь - создаем через обычную функцию
            user, is_new = await get_or_create_user(message.from_user, message.bot, referral_code)
            await message.answer(
                f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
                f"🎁 Тебе активирован <b>бесплатный период на {TRIAL_DAYS} дней</b>.\n"
                f"Нажми <b>«Мои ключи VPN»</b> чтобы получить ключ для подключения.\n\n"
                f"Выбери действие:",
                parse_mode="HTML",
                reply_markup=main_menu()
            )
            return
        
        # Пользователь существует - проверяем есть ли у него подписка
        sub_result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.expires_at.desc())
        )
        sub = sub_result.scalar_one_or_none()
        
        if not sub and not user.trial_used:
            # Пользователь есть, но подписки нет и триал не использован - создаем VPN
            print(f"[Start] Пользователь {user.id} без подписки, создаем VPN...")
            vpn_client = await xray.create_client(user.id, TRIAL_DAYS)
            
            if vpn_client:
                print(f"[Start] VPN клиент создан: {vpn_client['uuid']}")
                new_sub = Subscription(
                    user_id=user.id,
                    xray_uuid=vpn_client["uuid"],
                    vless_link=vpn_client["vless_link"],
                    plan_key="trial",
                    expires_at=datetime.now() + timedelta(days=TRIAL_DAYS),
                )
                session.add(new_sub)
                user.trial_used = True
                await session.commit()
                
                await message.answer(
                    f"🎉 Отлично! Твой VPN ключ готов!\n\n"
                    f"🎁 Тебе активирован <b>бесплатный период на {TRIAL_DAYS} дней</b>.\n"
                    f"Нажми <b>«Мои ключи VPN»</b> чтобы получить ключ для подключения.\n\n"
                    f"Выбери действие:",
                    parse_mode="HTML",
                    reply_markup=main_menu()
                )
            else:
                await message.answer(
                    f"❌ Не удалось создать VPN ключ. Попробуй позже или обратись в поддержку.",
                    parse_mode="HTML",
                    reply_markup=main_menu()
                )
        else:
            # Все ок, просто приветствие
            await message.answer(
                f"👋 С возвращением, <b>{message.from_user.first_name}</b>!\n\nВыбери действие:",
                parse_mode="HTML",
                reply_markup=main_menu()
            )


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "🌸Главное меню:",
        reply_markup=main_menu()
    )
    await callback.answer()


@router.message(Command("invite"))
async def invite_command(message: Message):
    """Команда /invite - открывает реферальную программу."""
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == message.from_user.id))
        user = result.scalar_one_or_none()
        
        if not user:
            await message.answer(
                "Сначала запусти бота командой /start",
                reply_markup=main_menu()
            )
            return
        
        ref_result = await session.execute(
            select(User).where(User.referred_by == user.id)
        )
        referrals = ref_result.scalars().all()

        bonus_result = await session.execute(
            select(ReferralBonus).where(ReferralBonus.referrer_id == user.id)
        )
        bonuses = bonus_result.scalars().all()
        total_bonus_days = sum(b.bonus_days for b in bonuses)

        bot_username = (await message.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user.referral_code}"
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from urllib.parse import quote
        share_url = f"https://t.me/share/url?url={quote(ref_link)}&text={quote('🌸 Попробуй Sakura VPN — быстрый и надёжный VPN!\n\n🎁 Регистрируйся по моей ссылке и получи бесплатный пробный период!')}"
        
        text = (
            f"👥 <b>Реферальная программа</b>\n\n"
            f"За каждого приглашённого друга — ты и он получаете <b>+3 дня VPN</b> бесплатно!\n\n"
            f"🔗 Твоя реферальная ссылка:\n"
            f"<code>{ref_link}</code>\n\n"
            f"📊 Статистика:\n"
            f"• Приглашено: <b>{len(referrals)} чел.</b>\n"
            f"• Заработано бонусов: <b>{total_bonus_days} дн.</b>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=share_url)],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")]
        ])
        
        await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


@router.message(Command("help"))
async def help_command(message: Message):
    """Команда /help - показывает поддержку."""
    await message.answer(
        "💬 <b>Поддержка</b>\n\n"
        "Если у тебя возникли вопросы или проблемы:\n\n"
        "📧 Email: sakuravpnsupp@gmail.com\n"
        "💬 Telegram: @sakuravpn_supp\n\n"
        "Мы отвечаем в течение 24 часов.",
        parse_mode="HTML",
        reply_markup=back_main()
    )
