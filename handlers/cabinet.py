from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from database.db import async_session
from database.models import User, Subscription, ReferralBonus
from keyboards.inline import cabinet_keyboard, back_main, main_menu

router = Router()


@router.callback_query(F.data == "cabinet")
async def show_cabinet(callback: CallbackQuery):
    async with async_session() as session:
        # Пользователь
        result = await session.execute(select(User).where(User.id == callback.from_user.id))
        user = result.scalar_one_or_none()
        if not user:
            await callback.answer("Сначала напиши /start", show_alert=True)
            return

        # Активная подписка
        sub_result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id, Subscription.is_active == True)
            .order_by(Subscription.expires_at.desc())
        )
        sub = sub_result.scalar_one_or_none()

        # Кол-во рефералов
        ref_count_result = await session.execute(
            select(User).where(User.referred_by == user.id)
        )
        ref_count = len(ref_count_result.scalars().all())

        # Формируем текст
        now = datetime.now(timezone.utc)
        if sub and sub.expires_at > now:
            time_left = sub.expires_at - now
            days_left = time_left.days
            hours_left = (time_left.seconds // 3600)
            time_str = f"{days_left} дн. {hours_left} ч." if hours_left > 0 else f"{days_left} дн."
            sub_status = f"✅ Активна — осталось <b>{time_str}</b>"
            has_active = True
        else:
            sub_status = "❌ Нет активной подписки"
            has_active = False

        text = (
            f"👤 <b>Личный кабинет</b>\n\n"
            f"🆔 ID: <code>{user.id}</code>\n"
            f"👤 Имя: {user.full_name or '—'}\n\n"
            f"📡 Подписка: {sub_status}\n"
            f"💰 Баланс: <b>{user.balance} ₽</b>\n"
            f"👥 Рефералов: <b>{ref_count}</b>\n\n"
            f"🔗 Твой реф. код: <code>{user.referral_code}</code>"
        )

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=cabinet_keyboard(has_active))
    await callback.answer()


@router.callback_query(F.data == "my_keys")
async def show_keys(callback: CallbackQuery):
    async with async_session() as session:
        sub_result = await session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == callback.from_user.id,
                Subscription.is_active == True,
                Subscription.expires_at > datetime.now()
            )
            .order_by(Subscription.expires_at.desc())
        )
        sub = sub_result.scalar_one_or_none()

        if not sub:
            await callback.message.edit_text(
                "❌ У тебя нет активной подписки.\n\nКупи подписку, чтобы получить VPN ключ.",
                reply_markup=back_main()
            )
            await callback.answer()
            return

        days_left = (sub.expires_at - datetime.now(timezone.utc)).days
        hours_left = ((sub.expires_at - datetime.now(timezone.utc)).seconds // 3600)
        time_str = f"{days_left} дн. {hours_left} ч." if hours_left > 0 else f"{days_left} дн."
        
        text = (
            f"🔑 <b>Твой VPN ключ</b>\n\n"
            f"<code>{sub.vless_link}</code>\n\n"
            f"⏳ Действует ещё: <b>{time_str}</b>\n\n"
            f"Нажми на ключ выше чтобы скопировать."
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Как подключиться?", callback_data="how_to_connect_keys")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")]
        ])
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "how_to_connect")
async def how_to_connect(callback: CallbackQuery):
    await callback.message.edit_text(
        "📱 <b>Выбери свою платформу:</b>\n\n"
        "Нажми на кнопку с твоим устройством для получения подробной инструкции.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 iPhone / iPad", callback_data="guide_ios:main")],
            [InlineKeyboardButton(text="🤖 Android", callback_data="guide_android:main")],
            [InlineKeyboardButton(text="💻 Windows / Mac", callback_data="guide_windows:main")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "how_to_connect_keys")
async def how_to_connect_keys(callback: CallbackQuery):
    await callback.message.edit_text(
        "📱 <b>Выбери свою платформу:</b>\n\n"
        "Нажми на кнопку с твоим устройством для получения подробной инструкции.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 iPhone / iPad", callback_data="guide_ios:keys")],
            [InlineKeyboardButton(text="🤖 Android", callback_data="guide_android:keys")],
            [InlineKeyboardButton(text="💻 Windows / Mac", callback_data="guide_windows:keys")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="my_keys")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("guide_ios:"))
async def guide_ios(callback: CallbackQuery):
    source = callback.data.split(":")[1]
    back_callback = "how_to_connect" if source == "main" else "how_to_connect_keys"
    
    await callback.message.edit_text(
        "📱 <b>Инструкция для iPhone/iPad</b>\n\n"
        "<b>Шаг 1:</b> Скачай приложение\n"
        "• Открой App Store\n"
        "• Найди <b>Streisand</b> или <b>FoXray</b>\n"
        "• Установи приложение\n\n"
        "<b>Шаг 2:</b> Добавь конфигурацию\n"
        "• Открой приложение\n"
        "• Нажми на <b>+</b> или <b>Add Server</b>\n"
        "• Выбери <b>Import from Clipboard</b>\n\n"
        "<b>Шаг 3:</b> Скопируй ключ\n"
        "• Вернись в бота\n"
        "• Нажми «Мои ключи VPN»\n"
        "• Нажми на ключ чтобы скопировать\n\n"
        "<b>Шаг 4:</b> Подключись\n"
        "• Вернись в приложение\n"
        "• Нажми на добавленный сервер\n"
        "• Нажми кнопку подключения\n"
        "• Разреши VPN соединение\n\n"
        "✅ Готово! VPN подключен.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Streisand", url="https://apps.apple.com/app/streisand/id6450534064")],
            [InlineKeyboardButton(text="📥 FoXray", url="https://apps.apple.com/app/foxray/id6448898396")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("guide_android:"))
async def guide_android(callback: CallbackQuery):
    source = callback.data.split(":")[1]
    back_callback = "how_to_connect" if source == "main" else "how_to_connect_keys"
    
    await callback.message.edit_text(
        "🤖 <b>Инструкция для Android</b>\n\n"
        "<b>Шаг 1:</b> Скачай приложение\n"
        "• Открой Google Play\n"
        "• Найди <b>v2rayNG</b>\n"
        "• Установи приложение\n\n"
        "<b>Шаг 2:</b> Скопируй ключ\n"
        "• Вернись в бота\n"
        "• Нажми «Мои ключи VPN»\n"
        "• Нажми на ключ чтобы скопировать\n\n"
        "<b>Шаг 3:</b> Добавь конфигурацию\n"
        "• Открой v2rayNG\n"
        "• Нажми на <b>+</b> в правом верхнем углу\n"
        "• Выбери <b>Import config from Clipboard</b>\n\n"
        "<b>Шаг 4:</b> Подключись\n"
        "• Нажми на добавленный сервер\n"
        "• Нажми кнопку подключения внизу\n"
        "• Разреши VPN соединение\n\n"
        "✅ Готово! VPN подключен.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 v2rayNG", url="https://play.google.com/store/apps/details?id=com.v2ray.ang")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("guide_windows:"))
async def guide_windows(callback: CallbackQuery):
    source = callback.data.split(":")[1]
    back_callback = "how_to_connect" if source == "main" else "how_to_connect_keys"
    
    await callback.message.edit_text(
        "💻 <b>Инструкция для Windows/Mac</b>\n\n"
        "<b>Шаг 1:</b> Скачай приложение\n"
        "• Перейди на сайт hiddify.com\n"
        "• Скачай <b>Hiddify</b> для своей ОС\n"
        "• Установи приложение\n\n"
        "<b>Шаг 2:</b> Скопируй ключ\n"
        "• Вернись в бота\n"
        "• Нажми «Мои ключи VPN»\n"
        "• Нажми на ключ чтобы скопировать\n\n"
        "<b>Шаг 3:</b> Добавь конфигурацию\n"
        "• Открой Hiddify\n"
        "• Нажми <b>New Profile</b>\n"
        "• Вставь скопированный ключ\n"
        "• Нажми <b>Add</b>\n\n"
        "<b>Шаг 4:</b> Подключись\n"
        "• Выбери добавленный профиль\n"
        "• Нажми кнопку <b>Connect</b>\n\n"
        "✅ Готово! VPN подключен.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📥 Hiddify (Windows)", url="https://github.com/hiddify/hiddify-next/releases/latest")],
            [InlineKeyboardButton(text="📥 Hiddify (Mac)", url="https://github.com/hiddify/hiddify-next/releases/latest")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)]
        ])
    )
    await callback.answer()


@router.callback_query(F.data == "support")
async def show_support(callback: CallbackQuery):
    await callback.message.edit_text(
        "💬 <b>Поддержка</b>\n\n"
        "Если у тебя возникли вопросы или проблемы:\n\n"
        "📧 Email: sakuravpnsupp@gmail.com\n"
        "💬 Telegram: @sakuravpn_supp\n\n"
        "Мы отвечаем в течение 24 часов.",
        parse_mode="HTML",
        reply_markup=back_main()
    )
    await callback.answer()


@router.callback_query(F.data == "referral")
async def show_referral(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == callback.from_user.id))
        user = result.scalar_one_or_none()

        ref_result = await session.execute(
            select(User).where(User.referred_by == user.id)
        )
        referrals = ref_result.scalars().all()

        bonus_result = await session.execute(
            select(ReferralBonus).where(ReferralBonus.referrer_id == user.id)
        )
        bonuses = bonus_result.scalars().all()
        total_bonus_days = sum(b.bonus_days for b in bonuses)

        bot_username = (await callback.bot.get_me()).username
        ref_link = f"https://t.me/{bot_username}?start={user.referral_code}"
        
        # Текст для шаринга
        share_text = f"🌸 Попробуй Sakura VPN — быстрый и надёжный VPN!\n\n🎁 Регистрируйся по моей ссылке и получи бесплатный пробный период!\n\n{ref_link}"

        text = (
            f"👥 <b>Реферальная программа</b>\n\n"
            f"За каждого приглашённого друга — ты и он получаете <b>+3 дня VPN</b> бесплатно!\n\n"
            f"🔗 Твоя реферальная ссылка:\n"
            f"<code>{ref_link}</code>\n\n"
            f"📊 Статистика:\n"
            f"• Приглашено: <b>{len(referrals)} чел.</b>\n"
            f"• Заработано бонусов: <b>{total_bonus_days} дн.</b>"
        )
        
        # Клавиатура с кнопкой "Поделиться" через tg://msg_url
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from urllib.parse import quote
        share_url = f"https://t.me/share/url?url={quote(ref_link)}&text={quote('🌸 Попробуй Sakura VPN — быстрый и надёжный VPN!\n\n🎁 Регистрируйся по моей ссылке и получи бесплатный пробный период!')}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=share_url)],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")]
        ])
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "how_to")
async def how_to_connect(callback: CallbackQuery):
    text = (
        "📱 <b>Как подключиться к VPN</b>\n\n"
        "<b>1. Получи ключ</b>\n"
        "Нажми «Мои ключи VPN» и скопируй ссылку\n\n"
        "<b>2. Установи приложение</b>\n"
        "• iPhone: <b>Streisand</b> (App Store)\n"
        "• Android: <b>v2rayNG</b> (Google Play)\n"
        "• Windows/Mac: <b>Hiddify</b> (hiddify.com)\n\n"
        "<b>3. Добавь конфигурацию</b>\n"
        "Открой приложение → нажми + → вставь скопированную ссылку\n\n"
        "<b>4. Подключись</b>\n"
        "Нажми кнопку подключения — готово! ✅\n\n"
        "❓ Если возникли проблемы — напиши в поддержку."
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_main())
    await callback.answer()
