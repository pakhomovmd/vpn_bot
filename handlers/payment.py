"""
Платёжный хэндлер — Cryptobot (Crypto Pay API).

Как работает цикл оплаты:
1. Пользователь выбирает тариф → бот создаёт счет в Cryptobot → отдаёт ссылку
2. Пользователь платит криптой
3. Пользователь нажимает «Я оплатил» → бот проверяет статус через API
4. Если оплачено → создаём/продлеваем VPN подписку
"""

from datetime import datetime, timedelta, timezone

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from config import PLANS
from database.db import async_session
from database.models import User, Subscription, Payment
from keyboards.inline import back_main
from services.vpn import xray
from services.cryptopay import cryptopay
from services.heleket import heleket
from services.cardlink import cardlink

router = Router()


def plans_keyboard_crypto() -> InlineKeyboardMarkup:
    """Клавиатура с тарифами."""
    buttons = []
    for key, plan in PLANS.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"{plan['title']} — {plan['price_rub']} ₽",
                callback_data=f"plan_select:{key}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_method_keyboard(plan_key: str) -> InlineKeyboardMarkup:
    """Выбор способа оплаты."""
    plan = PLANS[plan_key]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐️ Telegram Stars — {plan['price_stars']} ⭐️", callback_data=f"method_stars:{plan_key}")],
        [InlineKeyboardButton(text=f"🤖 CryptoBot — ${plan['price_usd']}", callback_data=f"crypto_cryptobot:{plan_key}")],
        [InlineKeyboardButton(text=f"💎 Любая криптовалюта — ${plan['price_usd']}", callback_data=f"crypto_heleket:{plan_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="buy")],
    ])


def currency_keyboard(plan_key: str) -> InlineKeyboardMarkup:
    """Выбор валюты для оплаты криптой."""
    plan = PLANS[plan_key]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💎 TON (${plan['price_usd']})", callback_data=f"pay:TON:{plan_key}")],
        [InlineKeyboardButton(text=f"💵 USDT (${plan['price_usd']})", callback_data=f"pay:USDT:{plan_key}")],
        [InlineKeyboardButton(text=f"₿ BTC (${plan['price_usd']})", callback_data=f"pay:BTC:{plan_key}")],
        [InlineKeyboardButton(text=f"💵 USDC (${plan['price_usd']})", callback_data=f"pay:USDC:{plan_key}")],
        [InlineKeyboardButton(text=f"🔺 TRX (${plan['price_usd']})", callback_data=f"pay:TRX:{plan_key}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"plan_select:{plan_key}")],
    ])


def payment_keyboard_crypto(pay_url: str, invoice_id: int) -> InlineKeyboardMarkup:
    """Кнопки для оплаты через крипту."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=pay_url)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_crypto:{invoice_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main")],
    ])


@router.callback_query(F.data == "buy")
async def show_plans(callback: CallbackQuery):
    await callback.message.edit_text(
        "💳 <b>Выбери тариф</b>\n\n"
        "🎯 Все тарифы включают:\n"
        "• Безлимитный трафик\n"
        "• Высокая скорость\n"
        "• Поддержка 24/7\n\n"
        "Выбери подходящий период:",
        parse_mode="HTML",
        reply_markup=plans_keyboard_crypto()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("plan_select:"))
async def select_plan(callback: CallbackQuery):
    plan_key = callback.data.split(":")[1]
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"💳 <b>Оплата подписки</b>\n\n"
        f"Тариф: <b>{plan['title']}</b>\n"
        f"Цена: <b>{plan['price_rub']} ₽</b>\n\n"
        f"Выбери способ оплаты:",
        parse_mode="HTML",
        reply_markup=payment_method_keyboard(plan_key)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("method_stars:"))
async def select_stars_method(callback: CallbackQuery):
    plan_key = callback.data.split(":")[1]
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    # Создаем инвойс для Telegram Stars
    from aiogram.types import LabeledPrice
    
    prices = [LabeledPrice(label=plan['title'], amount=plan['price_stars'])]
    
    try:
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"VPN подписка {plan['title']}",
            description=f"Подписка на {plan['title']} — безлимитный трафик, высокая скорость",
            payload=f"stars:{callback.from_user.id}:{plan_key}",
            provider_token="",  # Для Stars токен не нужен
            currency="XTR",  # Telegram Stars
            prices=prices
        )
        await callback.message.edit_text(
            f"⭐️ <b>Оплата через Telegram Stars</b>\n\n"
            f"Тариф: <b>{plan['title']}</b>\n"
            f"Цена: <b>{plan['price_stars']} ⭐️</b>\n\n"
            f"Счет отправлен ниже ⬇️\n"
            f"Нажми на него для оплаты.\n\n"
            f"Если передумал — нажми «Отмена»",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data=f"plan_select:{plan_key}")]
            ])
        )
        await callback.answer()
    except Exception as e:
        print(f"[Payment] Ошибка создания Stars инвойса: {e}")
        await callback.answer("Ошибка создания счета. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("method_cardlink:"))
async def select_cardlink_method(callback: CallbackQuery):
    plan_key = callback.data.split(":")[1]
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    print(f"[Payment] Начинаем создание Card Link счета для user_id={callback.from_user.id}, plan={plan_key}")
    await callback.message.edit_text("⏳ Создаю счет для оплаты...", parse_mode="HTML")

    # Создаем счет в Card Link
    order_id = f"cardlink_{callback.from_user.id}_{plan_key}_{int(callback.message.date.timestamp())}"
    print(f"[Payment] Вызываем cardlink.create_bill с amount={plan['price_rub']}, order_id={order_id}")
    
    bill = await cardlink.create_bill(
        amount=plan["price_rub"],
        order_id=order_id,
        description=f"VPN подписка {plan['title']}",
        custom=f"{callback.from_user.id}:{plan_key}"
    )
    print(f"[Payment] Результат cardlink.create_bill: {bill}")
    
    if not bill:
        await callback.message.edit_text(
            "❌ Не удалось создать счет. Попробуй позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data=f"plan_select:{plan_key}")]
            ])
        )
        await callback.answer()
        return

    # Сохраняем платёж в БД
    async with async_session() as session:
        db_payment = Payment(
            user_id=callback.from_user.id,
            yukassa_id=f"cardlink_{bill['bill_id']}",
            plan_key=plan_key,
            amount=plan["price_rub"],
            status="pending"
        )
        session.add(db_payment)
        await session.commit()

    await callback.message.edit_text(
        f"💳 <b>Оплата банковской картой</b>\n\n"
        f"Тариф: <b>{plan['title']}</b>\n"
        f"Цена: <b>{plan['price_rub']} ₽</b>\n\n"
        f"1️⃣ Нажми «Оплатить картой»\n"
        f"2️⃣ Введи данные карты на защищенной странице\n"
        f"3️⃣ Подтверди оплату\n"
        f"4️⃣ Вернись сюда и нажми «Проверить оплату»\n\n"
        f"💡 Принимаются карты любых банков",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить картой", url=bill["link_page_url"])],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_cardlink:{bill['bill_id']}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"plan_select:{plan_key}")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("crypto_cryptobot:"))
async def select_cryptobot(callback: CallbackQuery):
    plan_key = callback.data.split(":")[1]
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"🤖 <b>Оплата через CryptoBot</b>\n\n"
        f"Тариф: <b>{plan['title']}</b>\n"
        f"Цена: <b>${plan['price_usd']}</b>\n\n"
        f"Выбери валюту для оплаты:",
        parse_mode="HTML",
        reply_markup=currency_keyboard(plan_key)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("crypto_heleket:"))
async def select_heleket(callback: CallbackQuery):
    plan_key = callback.data.split(":")[1]
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    print(f"[Payment] Начинаем создание Heleket инвойса для user_id={callback.from_user.id}, plan={plan_key}")
    await callback.message.edit_text("⏳ Создаю счет для оплаты...", parse_mode="HTML")

    # Создаем инвойс в Heleket
    print(f"[Payment] Вызываем heleket.create_invoice с amount={plan['price_usd']}")
    invoice = await heleket.create_invoice(
        amount=plan["price_usd"],
        currency="USD",
        order_id=f"heleket_{callback.from_user.id}_{plan_key}_{int(callback.message.date.timestamp())}"
    )
    print(f"[Payment] Результат heleket.create_invoice: {invoice}")
    
    if not invoice:
        await callback.message.edit_text(
            "❌ Не удалось создать счет. Попробуй позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data=f"method_crypto:{plan_key}")]
            ])
        )
        await callback.answer()
        return

    # Сохраняем платёж в БД
    async with async_session() as session:
        db_payment = Payment(
            user_id=callback.from_user.id,
            yukassa_id=f"heleket_{invoice['uuid']}",
            plan_key=plan_key,
            amount=plan["price_usd"],
            status="pending"
        )
        session.add(db_payment)
        await session.commit()

    await callback.message.edit_text(
        f"💳 <b>Оплата криптовалютой</b>\n\n"
        f"Тариф: <b>{plan['title']}</b>\n"
        f"Цена: <b>${plan['price_usd']}</b>\n\n"
        f"1️⃣ Нажми «Открыть страницу оплаты»\n"
        f"2️⃣ Выбери криптовалюту и сеть\n"
        f"3️⃣ Оплати с любого кошелька\n"
        f"4️⃣ Вернись сюда и нажми «Проверить оплату»\n\n"
        f"💡 Поддерживаются все популярные криптовалюты и сети",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Открыть страницу оплаты", url=invoice["url"])],
            [InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_heleket:{invoice['uuid']}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"plan_select:{plan_key}")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("method_sbp:"))
async def select_sbp_method(callback: CallbackQuery):
    plan_key = callback.data.split(":")[1]
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"🏦 <b>Оплата через СБП</b>\n\n"
        f"Тариф: <b>{plan['title']}</b>\n"
        f"Цена: <b>{plan['price_rub']} ₽</b>\n\n"
        f"⚠️ Оплата через СБП временно недоступна по юридическим причинам.\n"
        f"Используйте оплату через Telegram Stars или криптовалюту.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⭐️ Оплатить Stars", callback_data=f"method_stars:{plan_key}")],
            [InlineKeyboardButton(text="💎 Оплатить криптой", callback_data=f"method_crypto:{plan_key}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"plan_select:{plan_key}")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay:"))
async def create_payment(callback: CallbackQuery):
    # Формат: pay:CURRENCY:plan_key
    parts = callback.data.split(":")
    currency = parts[1]
    plan_key = parts[2]
    
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return

    await callback.message.edit_text("⏳ Создаю счет для оплаты...", parse_mode="HTML")

    # Создаем счет в Cryptobot - сумма в USD, валюта выбранная пользователем
    # CryptoBot автоматически конвертирует по текущему курсу
    invoice = await cryptopay.create_invoice(
        amount=plan["price_usd"],
        currency=currency,
        description=f"VPN подписка {plan['title']}",
        payload=f"{callback.from_user.id}:{plan_key}:{currency}"
    )
    
    if not invoice:
        await callback.message.edit_text(
            "❌ Не удалось создать счет. Попробуй позже.",
            reply_markup=back_main()
        )
        await callback.answer()
        return

    # Сохраняем платёж в БД
    async with async_session() as session:
        db_payment = Payment(
            user_id=callback.from_user.id,
            yukassa_id=str(invoice["invoice_id"]),  # Используем это поле для invoice_id
            plan_key=plan_key,
            amount=plan["price"],
            status="pending"
        )
        session.add(db_payment)
        await session.commit()

    await callback.message.edit_text(
        f"💳 <b>Оплата подписки</b>\n\n"
        f"Тариф: <b>{plan['title']}</b>\n"
        f"Цена: <b>${plan['price_usd']}</b>\n"
        f"Оплата в: <b>{currency}</b>\n\n"
        f"1️⃣ Нажми «Оплатить»\n"
        f"2️⃣ Оплати в @CryptoBot (сумма конвертируется автоматически)\n"
        f"3️⃣ Вернись сюда и нажми «Я оплатил»",
        parse_mode="HTML",
        reply_markup=payment_keyboard_crypto(invoice["pay_url"], invoice["invoice_id"])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("check_crypto:"))
async def check_payment_crypto(callback: CallbackQuery):
    invoice_id = int(callback.data.split(":")[1])

    await callback.answer("⏳ Проверяю платёж...")

    # Проверяем статус в Cryptobot
    invoice = await cryptopay.get_invoice(invoice_id)
    
    if not invoice or invoice["status"] != "paid":
        await callback.message.edit_text(
            "⏳ Платёж ещё не прошёл. Подожди немного и попробуй снова.\n\n"
            "Если оплатил, но статус не обновляется — напиши в поддержку.",
            reply_markup=back_main()
        )
        return

    # Платёж прошёл — активируем подписку
    async with async_session() as session:
        # Обновляем статус платежа
        pay_result = await session.execute(
            select(Payment).where(Payment.yukassa_id == str(invoice_id))
        )
        db_payment = pay_result.scalar_one_or_none()
        
        if not db_payment:
            await callback.message.edit_text(
                "❌ Платёж не найден в базе. Обратись в поддержку.",
                reply_markup=back_main()
            )
            return
            
        if db_payment.status == "succeeded":
            await callback.message.edit_text(
                "✅ Подписка уже активирована!", 
                reply_markup=back_main()
            )
            return

        db_payment.status = "succeeded"
        db_payment.paid_at = datetime.now(timezone.utc)

        plan = PLANS[db_payment.plan_key]

        # Проверяем есть ли уже активная подписка (продлеваем)
        sub_result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == callback.from_user.id, Subscription.is_active == True)
            .order_by(Subscription.expires_at.desc())
        )
        existing_sub = sub_result.scalar_one_or_none()

        if existing_sub:
            # Продлеваем
            existing_sub.expires_at += timedelta(days=plan["days"])
            existing_sub.plan_key = db_payment.plan_key
            await xray.extend_client(existing_sub.xray_uuid, plan["days"])
            action = "продлена"
            print(f"[Payment] Подписка продлена для user_id={callback.from_user.id}, plan={plan['title']}")
        else:
            # Создаём новую
            vpn_client = await xray.create_client(callback.from_user.id, plan["days"])
            if vpn_client:
                new_sub = Subscription(
                    user_id=callback.from_user.id,
                    xray_uuid=vpn_client["uuid"],
                    vless_link=vpn_client["vless_link"],
                    plan_key=db_payment.plan_key,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=plan["days"]),
                )
                session.add(new_sub)
                action = "активирована"
                print(f"[Payment] Новая подписка создана для user_id={callback.from_user.id}, plan={plan['title']}")
            else:
                await callback.message.edit_text(
                    "❌ Платёж прошёл, но не удалось создать VPN ключ. Обратись в поддержку.",
                    reply_markup=back_main()
                )
                return

        await session.commit()

    await callback.message.edit_text(
        f"✅ <b>Подписка {action}!</b>\n\n"
        f"Тариф: <b>{plan['title']}</b>\n"
        f"Срок: <b>{plan['days']} дней</b>\n\n"
        f"Нажми «Мои ключи VPN» чтобы получить ключ.",
        parse_mode="HTML",
        reply_markup=back_main()
    )


@router.callback_query(F.data.startswith("check_heleket:"))
async def check_payment_heleket(callback: CallbackQuery):
    uuid = callback.data.split(":")[1]

    await callback.answer("⏳ Проверяю платёж...")

    # Проверяем статус в Heleket
    invoice = await heleket.get_invoice(uuid)
    
    if not invoice or invoice["payment_status"] != "paid":
        await callback.message.edit_text(
            "⏳ Платёж ещё не прошёл. Подожди немного и попробуй снова.\n\n"
            "Если оплатил, но статус не обновляется — напиши в поддержку.",
            reply_markup=back_main()
        )
        return

    # Платёж прошёл — активируем подписку
    async with async_session() as session:
        # Обновляем статус платежа
        pay_result = await session.execute(
            select(Payment).where(Payment.yukassa_id == f"heleket_{uuid}")
        )
        db_payment = pay_result.scalar_one_or_none()
        
        if not db_payment:
            await callback.message.edit_text(
                "❌ Платёж не найден в базе. Обратись в поддержку.",
                reply_markup=back_main()
            )
            return
            
        if db_payment.status == "succeeded":
            await callback.message.edit_text(
                "✅ Подписка уже активирована!", 
                reply_markup=back_main()
            )
            return

        db_payment.status = "succeeded"
        db_payment.paid_at = datetime.now(timezone.utc)

        plan = PLANS[db_payment.plan_key]

        # Проверяем есть ли уже активная подписка (продлеваем)
        sub_result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == callback.from_user.id, Subscription.is_active == True)
            .order_by(Subscription.expires_at.desc())
        )
        existing_sub = sub_result.scalar_one_or_none()

        if existing_sub:
            # Продлеваем
            existing_sub.expires_at += timedelta(days=plan["days"])
            existing_sub.plan_key = db_payment.plan_key
            await xray.extend_client(existing_sub.xray_uuid, plan["days"])
            action = "продлена"
            print(f"[Payment] Подписка продлена для user_id={callback.from_user.id}, plan={plan['title']}")
        else:
            # Создаём новую
            vpn_client = await xray.create_client(callback.from_user.id, plan["days"])
            if vpn_client:
                new_sub = Subscription(
                    user_id=callback.from_user.id,
                    xray_uuid=vpn_client["uuid"],
                    vless_link=vpn_client["vless_link"],
                    plan_key=db_payment.plan_key,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=plan["days"]),
                )
                session.add(new_sub)
                action = "активирована"
                print(f"[Payment] Новая подписка создана для user_id={callback.from_user.id}, plan={plan['title']}")
            else:
                await callback.message.edit_text(
                    "❌ Платёж прошёл, но не удалось создать VPN ключ. Обратись в поддержку.",
                    reply_markup=back_main()
                )
                return

        await session.commit()

    await callback.message.edit_text(
        f"✅ <b>Подписка {action}!</b>\n\n"
        f"Тариф: <b>{plan['title']}</b>\n"
        f"Срок: <b>{plan['days']} дней</b>\n\n"
        f"Нажми «Мои ключи VPN» чтобы получить ключ.",
        parse_mode="HTML",
        reply_markup=back_main()
    )


@router.callback_query(F.data.startswith("check_cardlink:"))
async def check_payment_cardlink(callback: CallbackQuery):
    bill_id = callback.data.split(":")[1]

    await callback.answer("⏳ Проверяю платёж...")

    # Проверяем статус в Card Link
    bill = await cardlink.get_bill_status(bill_id)
    
    if not bill or bill["status"] not in ["SUCCESS", "OVERPAID"]:
        await callback.message.edit_text(
            "⏳ Платёж ещё не прошёл. Подожди немного и попробуй снова.\n\n"
            "Если оплатил, но статус не обновляется — напиши в поддержку.",
            reply_markup=back_main()
        )
        return

    # Платёж прошёл — активируем подписку
    async with async_session() as session:
        # Обновляем статус платежа
        pay_result = await session.execute(
            select(Payment).where(Payment.yukassa_id == f"cardlink_{bill_id}")
        )
        db_payment = pay_result.scalar_one_or_none()
        
        if not db_payment:
            await callback.message.edit_text(
                "❌ Платёж не найден в базе. Обратись в поддержку.",
                reply_markup=back_main()
            )
            return
            
        if db_payment.status == "succeeded":
            await callback.message.edit_text(
                "✅ Подписка уже активирована!", 
                reply_markup=back_main()
            )
            return

        db_payment.status = "succeeded"
        db_payment.paid_at = datetime.now(timezone.utc)

        plan = PLANS[db_payment.plan_key]

        # Проверяем есть ли уже активная подписка (продлеваем)
        sub_result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == callback.from_user.id, Subscription.is_active == True)
            .order_by(Subscription.expires_at.desc())
        )
        existing_sub = sub_result.scalar_one_or_none()

        if existing_sub:
            # Продлеваем
            existing_sub.expires_at += timedelta(days=plan["days"])
            existing_sub.plan_key = db_payment.plan_key
            await xray.extend_client(existing_sub.xray_uuid, plan["days"])
            action = "продлена"
            print(f"[Payment] Подписка продлена для user_id={callback.from_user.id}, plan={plan['title']}")
        else:
            # Создаём новую
            vpn_client = await xray.create_client(callback.from_user.id, plan["days"])
            if vpn_client:
                new_sub = Subscription(
                    user_id=callback.from_user.id,
                    xray_uuid=vpn_client["uuid"],
                    vless_link=vpn_client["vless_link"],
                    plan_key=db_payment.plan_key,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=plan["days"]),
                )
                session.add(new_sub)
                action = "активирована"
                print(f"[Payment] Новая подписка создана для user_id={callback.from_user.id}, plan={plan['title']}")
            else:
                await callback.message.edit_text(
                    "❌ Платёж прошёл, но не удалось создать VPN ключ. Обратись в поддержку.",
                    reply_markup=back_main()
                )
                return

        await session.commit()

    await callback.message.edit_text(
        f"✅ <b>Подписка {action}!</b>\n\n"
        f"Тариф: <b>{plan['title']}</b>\n"
        f"Срок: <b>{plan['days']} дней</b>\n\n"
        f"Нажми «Мои ключи VPN» чтобы получить ключ.",
        parse_mode="HTML",
        reply_markup=back_main()
    )


# Обработчик успешной оплаты через Telegram Stars
@router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message):
    """Обработка успешной оплаты через Telegram Stars."""
    payment_info = message.successful_payment
    
    # Парсим payload: "stars:user_id:plan_key"
    payload_parts = payment_info.invoice_payload.split(":")
    if len(payload_parts) != 3 or payload_parts[0] != "stars":
        print(f"[Payment] Неверный формат payload: {payment_info.invoice_payload}")
        return
    
    user_id = int(payload_parts[1])
    plan_key = payload_parts[2]
    plan = PLANS.get(plan_key)
    
    if not plan:
        print(f"[Payment] Тариф не найден: {plan_key}")
        return
    
    print(f"[Payment] Успешная оплата Stars: user_id={user_id}, plan={plan_key}, amount={payment_info.total_amount}")
    
    # Сохраняем платёж в БД
    async with async_session() as session:
        db_payment = Payment(
            user_id=user_id,
            yukassa_id=f"stars_{payment_info.telegram_payment_charge_id}",
            plan_key=plan_key,
            amount=payment_info.total_amount,
            status="succeeded",
            paid_at=datetime.now(timezone.utc)
        )
        session.add(db_payment)
        
        # Проверяем есть ли уже активная подписка (продлеваем)
        sub_result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id, Subscription.is_active == True)
            .order_by(Subscription.expires_at.desc())
        )
        existing_sub = sub_result.scalar_one_or_none()

        if existing_sub:
            # Продлеваем
            existing_sub.expires_at += timedelta(days=plan["days"])
            existing_sub.plan_key = plan_key
            await xray.extend_client(existing_sub.xray_uuid, plan["days"])
            action = "продлена"
            print(f"[Payment] Подписка продлена для user_id={user_id}, plan={plan['title']}")
        else:
            # Создаём новую
            vpn_client = await xray.create_client(user_id, plan["days"])
            if vpn_client:
                new_sub = Subscription(
                    user_id=user_id,
                    xray_uuid=vpn_client["uuid"],
                    vless_link=vpn_client["vless_link"],
                    plan_key=plan_key,
                    expires_at=datetime.now(timezone.utc) + timedelta(days=plan["days"]),
                )
                session.add(new_sub)
                action = "активирована"
                print(f"[Payment] Новая подписка создана для user_id={user_id}, plan={plan['title']}")
            else:
                await message.answer(
                    "❌ Платёж прошёл, но не удалось создать VPN ключ. Обратись в поддержку.",
                    reply_markup=back_main()
                )
                return

        await session.commit()

    await message.answer(
        f"✅ <b>Подписка {action}!</b>\n\n"
        f"Тариф: <b>{plan['title']}</b>\n"
        f"Срок: <b>{plan['days']} дней</b>\n\n"
        f"Нажми «Мои ключи VPN» чтобы получить ключ.",
        parse_mode="HTML",
        reply_markup=back_main()
    )
