from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func

from config import ADMIN_ID
from database.db import async_session
from database.models import User, Subscription, Payment
from keyboards.inline import admin_keyboard, back_main

router = Router()


class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_user_id = State()
    waiting_for_days = State()
    waiting_for_ban_reason = State()
    waiting_for_search_query = State()


def admin_only(handler):
    """Декоратор — только для админа."""
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id if hasattr(event, 'from_user') else 0
        if user_id != ADMIN_ID:
            return
        return await handler(event, *args, **kwargs)
    return wrapper


@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    await message.answer("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    async with async_session() as session:
        total_users = (await session.execute(select(func.count(User.id)))).scalar()
        active_subs = (await session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.is_active == True,
                Subscription.expires_at > datetime.now(timezone.utc)
            )
        )).scalar()
        total_revenue = (await session.execute(
            select(func.sum(Payment.amount)).where(Payment.status == "succeeded")
        )).scalar() or 0

        today_users = (await session.execute(
            select(func.count(User.id)).where(
                func.date(User.created_at) == datetime.now(timezone.utc).date()
            )
        )).scalar()
        
        # Статистика по платежам
        stars_payments = (await session.execute(
            select(func.count(Payment.id)).where(
                Payment.status == "succeeded",
                Payment.yukassa_id.like("stars_%")
            )
        )).scalar() or 0
        
        crypto_payments = (await session.execute(
            select(func.count(Payment.id)).where(
                Payment.status == "succeeded",
                Payment.yukassa_id.notlike("stars_%")
            )
        )).scalar() or 0

    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🆕 Новых сегодня: <b>{today_users}</b>\n"
        f"📡 Активных подписок: <b>{active_subs}</b>\n\n"
        f"💰 <b>Платежи:</b>\n"
        f"⭐️ Telegram Stars: <b>{stars_payments}</b>\n"
        f"💎 Криптовалюта: <b>{crypto_payments}</b>\n"
        f"💵 Общий доход: <b>${total_revenue}</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\n"
        "Отправь мне текст для рассылки.\n"
        "Поддерживается HTML форматирование.\n\n"
        "Для отмены напиши /admin",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_find_user")
async def admin_find_user_prompt(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return

    # Показываем меню выбора способа поиска
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 По username", callback_data="search_by_username")],
        [InlineKeyboardButton(text="👤 По имени", callback_data="search_by_name")],
        [InlineKeyboardButton(text="🆔 По Telegram ID", callback_data="search_by_id")],
        [InlineKeyboardButton(text="📋 Последние 20", callback_data="search_recent")],
        [InlineKeyboardButton(text="✅ С активной подпиской", callback_data="search_active")],
        [InlineKeyboardButton(text="⏰ Истекает скоро", callback_data="search_expiring")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_admin")]
    ])

    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Выбери способ поиска:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "search_by_id")
async def search_by_id(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_user_id)
    await callback.message.edit_text(
        "🆔 <b>Поиск по Telegram ID</b>\n\n"
        "Отправь мне Telegram ID пользователя.\n\n"
        "Для отмены напиши /admin",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "search_by_username")
async def search_by_username(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_search_query)
    await state.update_data(search_type="username")
    await callback.message.edit_text(
        "🔍 <b>Поиск по username</b>\n\n"
        "Отправь мне username (без @) или его часть.\n\n"
        "Для отмены напиши /admin",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "search_by_name")
async def search_by_name(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await state.set_state(AdminStates.waiting_for_search_query)
    await state.update_data(search_type="name")
    await callback.message.edit_text(
        "👤 <b>Поиск по имени</b>\n\n"
        "Отправь мне имя пользователя или его часть.\n\n"
        "Для отмены напиши /admin",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "search_recent")
async def search_recent(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    async with async_session() as session:
        result = await session.execute(
            select(User)
            .order_by(User.created_at.desc())
            .limit(20)
        )
        users = result.scalars().all()

    if not users:
        await callback.message.edit_text(
            "❌ Пользователи не найдены.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_find_user")]
            ])
        )
        await callback.answer()
        return

    await show_user_list(callback.message, users, "📋 Последние 20 пользователей")
    await callback.answer()


@router.callback_query(F.data == "search_active")
async def search_active(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    async with async_session() as session:
        result = await session.execute(
            select(User)
            .join(Subscription, User.id == Subscription.user_id)
            .where(
                Subscription.is_active == True,
                Subscription.expires_at > datetime.now(timezone.utc)
            )
            .order_by(Subscription.expires_at.desc())
        )
        users = result.scalars().all()

    if not users:
        await callback.message.edit_text(
            "❌ Нет пользователей с активной подпиской.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_find_user")]
            ])
        )
        await callback.answer()
        return

    await show_user_list(callback.message, users, "✅ Пользователи с активной подпиской")
    await callback.answer()


@router.callback_query(F.data == "search_expiring")
async def search_expiring(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return

    from datetime import timedelta
    expiring_date = datetime.now(timezone.utc) + timedelta(days=3)

    async with async_session() as session:
        result = await session.execute(
            select(User)
            .join(Subscription, User.id == Subscription.user_id)
            .where(
                Subscription.is_active == True,
                Subscription.expires_at > datetime.now(timezone.utc),
                Subscription.expires_at <= expiring_date
            )
            .order_by(Subscription.expires_at.asc())
        )
        users = result.scalars().all()

    if not users:
        await callback.message.edit_text(
            "❌ Нет пользователей с истекающей подпиской.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_find_user")]
            ])
        )
        await callback.answer()
        return

    await show_user_list(callback.message, users, "⏰ Подписка истекает в течение 3 дней")
    await callback.answer()


async def show_user_list(message, users, title: str):
    """Показывает список пользователей с кнопками для выбора."""
    buttons = []
    for user in users:
        user_label = f"@{user.username}" if user.username else user.full_name or f"ID: {user.id}"
        buttons.append([
            InlineKeyboardButton(
                text=user_label[:30],  # Ограничиваем длину
                callback_data=f"select_user:{user.id}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_find_user")])

    await message.edit_text(
        f"<b>{title}</b>\n\n"
        f"Найдено: <b>{len(users)}</b>\n"
        f"Выбери пользователя:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.callback_query(F.data.startswith("select_user:"))
async def select_user(callback: CallbackQuery):
    """Обработчик выбора пользователя из списка."""
    if callback.from_user.id != ADMIN_ID:
        return

    user_id = int(callback.data.split(":")[1])

    # Используем существующую логику показа информации о пользователе
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        # Получаем подписку из БД
        sub_result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id, Subscription.is_active == True)
            .order_by(Subscription.expires_at.desc())
        )
        sub = sub_result.scalar_one_or_none()

        # Синхронизируем с 3X-UI панелью если есть подписка
        if sub:
            from services.vpn import xray
            panel_info = await xray.get_client_info(sub.xray_uuid)

            if panel_info:
                panel_expiry_ms = panel_info.get("expiryTime", 0)
                if panel_expiry_ms > 0:
                    panel_expires_at = datetime.fromtimestamp(panel_expiry_ms / 1000, tz=timezone.utc)

                    if abs((sub.expires_at - panel_expires_at).total_seconds()) > 60:
                        print(f"[Admin] Синхронизация: обновляем expires_at для user_id={user_id}")
                        sub.expires_at = panel_expires_at
                        await session.commit()

                if not panel_info.get("enable", True):
                    sub.is_active = False
                    await session.commit()

        # Формируем информацию о подписке
        if sub and sub.expires_at > datetime.now(timezone.utc):
            time_left = sub.expires_at - datetime.now(timezone.utc)
            days_left = time_left.days
            hours_left = (time_left.seconds // 3600)
            sub_info = f"✅ Активна — {days_left} дн. {hours_left} ч."
        else:
            sub_info = "❌ Нет активной подписки"

    await callback.message.edit_text(
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Имя: {user.full_name or '—'}\n"
        f"📱 Username: @{user.username or '—'}\n"
        f"📡 Подписка: {sub_info}\n"
        f"🎁 Триал использован: {'Да' if user.trial_used else 'Нет'}\n"
        f"🔗 Реф. код: <code>{user.referral_code}</code>\n"
        f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M') if user.created_at else '—'}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Выдать дни", callback_data=f"admin_give_days:{user_id}")],
            [InlineKeyboardButton(text="🔄 Сбросить триал", callback_data=f"admin_reset_trial:{user_id}")],
            [InlineKeyboardButton(text="🚫 Забанить", callback_data=f"admin_ban:{user_id}")],
            [InlineKeyboardButton(text="✅ Разбанить", callback_data=f"admin_unban:{user_id}")],
            [InlineKeyboardButton(text="◀️ Поиск", callback_data="admin_find_user")]
        ])
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_search_query)
async def process_search_query(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    if message.text == "/admin":
        await state.clear()
        await message.answer("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_keyboard())
        return

    data = await state.get_data()
    search_type = data.get("search_type")
    query = message.text.strip().lower()

    async with async_session() as session:
        if search_type == "username":
            result = await session.execute(
                select(User).where(User.username.ilike(f"%{query}%"))
            )
        else:  # name
            result = await session.execute(
                select(User).where(User.full_name.ilike(f"%{query}%"))
            )

        users = result.scalars().all()

    await state.clear()

    if not users:
        await message.answer(
            f"❌ Пользователи не найдены по запросу: <code>{message.text}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Поиск", callback_data="admin_find_user")]
            ])
        )
        return

    # Показываем список найденных пользователей
    buttons = []
    for user in users[:20]:  # Ограничиваем 20 результатами
        user_label = f"@{user.username}" if user.username else user.full_name or f"ID: {user.id}"
        buttons.append([
            InlineKeyboardButton(
                text=user_label[:30],
                callback_data=f"select_user:{user.id}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="◀️ Поиск", callback_data="admin_find_user")])

    search_label = "username" if search_type == "username" else "имени"
    await message.answer(
        f"🔍 <b>Результаты поиска по {search_label}</b>\n\n"
        f"Запрос: <code>{message.text}</code>\n"
        f"Найдено: <b>{len(users)}</b>\n\n"
        f"Выбери пользователя:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


@router.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    
    if message.text == "/admin":
        await state.clear()
        await message.answer("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_keyboard())
        return
    
    text = message.text
    await message.answer("⏳ Начинаю рассылку...")
    
    async with async_session() as session:
        result = await session.execute(select(User.id).where(User.is_banned == False))
        user_ids = result.scalars().all()

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await state.clear()
    await message.answer(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"Отправлено: <b>{sent}</b>\n"
        f"Ошибок: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=admin_keyboard()
    )


@router.message(AdminStates.waiting_for_user_id)
async def process_find_user(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    if message.text == "/admin":
        await state.clear()
        await message.answer("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_keyboard())
        return

    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("❌ Неверный формат ID. Введи число.")
        return

    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(
                f"❌ Пользователь с ID <code>{user_id}</code> не найден.",
                parse_mode="HTML"
            )
            return

        # Получаем подписку из БД
        sub_result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id, Subscription.is_active == True)
            .order_by(Subscription.expires_at.desc())
        )
        sub = sub_result.scalar_one_or_none()

        # Синхронизируем с 3X-UI панелью если есть подписка
        if sub:
            from services.vpn import xray
            panel_info = await xray.get_client_info(sub.xray_uuid)

            if panel_info:
                # Обновляем данные из панели
                panel_expiry_ms = panel_info.get("expiryTime", 0)
                if panel_expiry_ms > 0:
                    panel_expires_at = datetime.fromtimestamp(panel_expiry_ms / 1000, tz=timezone.utc)

                    # Если данные в панели отличаются - обновляем БД
                    if abs((sub.expires_at - panel_expires_at).total_seconds()) > 60:
                        print(f"[Admin] Синхронизация: обновляем expires_at для user_id={user_id}")
                        print(f"  БД: {sub.expires_at}, Панель: {panel_expires_at}")
                        sub.expires_at = panel_expires_at
                        await session.commit()

                # Проверяем статус enable
                if not panel_info.get("enable", True):
                    sub.is_active = False
                    await session.commit()

        # Формируем информацию о подписке
        if sub and sub.expires_at > datetime.now(timezone.utc):
            time_left = sub.expires_at - datetime.now(timezone.utc)
            days_left = time_left.days
            hours_left = (time_left.seconds // 3600)
            sub_info = f"✅ Активна — {days_left} дн. {hours_left} ч."
        else:
            sub_info = "❌ Нет активной подписки"

    await state.clear()
    await message.answer(
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👤 Имя: {user.full_name or '—'}\n"
        f"📱 Username: @{user.username or '—'}\n"
        f"📡 Подписка: {sub_info}\n"
        f"🎁 Триал использован: {'Да' if user.trial_used else 'Нет'}\n"
        f"🔗 Реф. код: <code>{user.referral_code}</code>\n"
        f"📅 Регистрация: {user.created_at.strftime('%d.%m.%Y %H:%M') if user.created_at else '—'}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Выдать дни", callback_data=f"admin_give_days:{user_id}")],
            [InlineKeyboardButton(text="🔄 Сбросить триал", callback_data=f"admin_reset_trial:{user_id}")],
            [InlineKeyboardButton(text="🚫 Забанить", callback_data=f"admin_ban:{user_id}")],
            [InlineKeyboardButton(text="✅ Разбанить", callback_data=f"admin_unban:{user_id}")],
            [InlineKeyboardButton(text="◀️ Админ-панель", callback_data="back_admin")]
        ])
    )


@router.callback_query(F.data == "back_admin")
async def back_to_admin(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.edit_text("🛠 <b>Админ-панель</b>", parse_mode="HTML", reply_markup=admin_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("admin_give_days:"))
async def admin_give_days(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    
    user_id = int(callback.data.split(":")[1])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_days)
    
    await callback.message.edit_text(
        f"➕ <b>Выдать дни подписки</b>\n\n"
        f"Пользователь ID: <code>{user_id}</code>\n\n"
        f"Введи количество дней для добавления:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminStates.waiting_for_days)
async def process_give_days(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        days = int(message.text)
        if days <= 0:
            await message.answer("❌ Количество дней должно быть больше 0")
            return
    except ValueError:
        await message.answer("❌ Введи число")
        return

    data = await state.get_data()
    user_id = data.get("target_user_id")

    async with async_session() as session:
        # Проверяем существует ли пользователь
        user_result = await session.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            await message.answer(
                f"❌ Пользователь <code>{user_id}</code> не найден в базе.",
                parse_mode="HTML",
                reply_markup=admin_keyboard()
            )
            await state.clear()
            return

        # Ищем ВСЕ подписки пользователя (не только активные)
        sub_result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.expires_at.desc())
        )
        sub = sub_result.scalar_one_or_none()

        from datetime import timedelta
        from services.vpn import xray

        # Проверяем есть ли клиент в панели 3X-UI (по email)
        email = f"user_{user_id}"
        panel_client = await xray.find_client_by_email(email)

        if panel_client:
            # Клиент существует в панели
            client_uuid = panel_client.get("id")
            print(f"[Admin] Найден клиент в панели: uuid={client_uuid}")

            if sub:
                # Обновляем существующую запись в БД
                print(f"[Admin] Обновляем существующую запись в БД для user_id={user_id}")
                sub.xray_uuid = client_uuid
                sub.is_active = True

                # Получаем текущий срок из панели и добавляем дни
                panel_expiry_ms = panel_client.get("expiryTime", 0)
                if panel_expiry_ms > 0:
                    current_expires = datetime.fromtimestamp(panel_expiry_ms / 1000, tz=timezone.utc)
                    # Если срок уже истек, начинаем с текущего момента
                    if current_expires < datetime.now(timezone.utc):
                        new_expires = datetime.now(timezone.utc) + timedelta(days=days)
                    else:
                        new_expires = current_expires + timedelta(days=days)
                else:
                    new_expires = datetime.now(timezone.utc) + timedelta(days=days)

                sub.expires_at = new_expires

                # Обновляем VLESS ссылку
                import aiohttp
                cookie_jar = aiohttp.CookieJar(unsafe=True)
                async with aiohttp.ClientSession(connector=xray._connector(), cookie_jar=cookie_jar) as link_session:
                    await xray._login(link_session)
                    sub.vless_link = await xray._build_vless_link(link_session, client_uuid, email)
            else:
                # Клиент есть в панели, но нет в БД - создаем запись
                print(f"[Admin] Клиент есть в панели, но нет в БД - создаем запись")
                panel_expiry_ms = panel_client.get("expiryTime", 0)
                if panel_expiry_ms > 0:
                    current_expires = datetime.fromtimestamp(panel_expiry_ms / 1000, tz=timezone.utc)
                    if current_expires < datetime.now(timezone.utc):
                        expires_at = datetime.now(timezone.utc) + timedelta(days=days)
                    else:
                        expires_at = current_expires + timedelta(days=days)
                else:
                    expires_at = datetime.now(timezone.utc) + timedelta(days=days)

                # Получаем VLESS ссылку
                import aiohttp
                cookie_jar = aiohttp.CookieJar(unsafe=True)
                async with aiohttp.ClientSession(connector=xray._connector(), cookie_jar=cookie_jar) as link_session:
                    await xray._login(link_session)
                    vless_link = await xray._build_vless_link(link_session, client_uuid, email)

                sub = Subscription(
                    user_id=user_id,
                    xray_uuid=client_uuid,
                    vless_link=vless_link,
                    plan_key="admin",
                    expires_at=expires_at,
                    is_active=True
                )
                session.add(sub)

            # Продлеваем в панели (устанавливаем новый срок)
            print(f"[Admin] Обновляем срок в панели для клиента {client_uuid}")
            new_expiry_ms = int(sub.expires_at.timestamp() * 1000)

            # Используем прямой API вызов для обновления срока с полными данными клиента
            from config import XRAY_INBOUND_ID, MAX_DEVICES
            cookie_jar = aiohttp.CookieJar(unsafe=True)
            import aiohttp
            import json as json_mod
            async with aiohttp.ClientSession(connector=xray._connector(), cookie_jar=cookie_jar) as panel_session:
                if await xray._login(panel_session):
                    try:
                        # Формируем полные данные клиента для обновления
                        client_data = {
                            "id": client_uuid,
                            "email": email,
                            "expiryTime": new_expiry_ms,
                            "enable": True,
                            "limitIp": MAX_DEVICES,
                            "totalGB": 0,
                            "flow": "xtls-rprx-vision",
                            "tgId": str(user_id),
                            "subId": "",
                            "reset": 0
                        }

                        resp = await panel_session.post(
                            xray._url(f"/panel/api/inbounds/updateClient/{client_uuid}"),
                            json={
                                "id": XRAY_INBOUND_ID,
                                "settings": json_mod.dumps({"clients": [client_data]})
                            },
                        )
                        data = await resp.json()
                        success = data.get("success", False)
                        print(f"[Admin] Результат обновления в панели: {data}")
                    except Exception as e:
                        print(f"[Admin] Ошибка обновления срока в панели: {e}")
                        import traceback
                        traceback.print_exc()
                        success = False
                else:
                    success = False

            if not success:
                await message.answer(
                    f"❌ Не удалось обновить срок в панели 3X-UI.\n"
                    f"Проверь логи панели.",
                    parse_mode="HTML",
                    reply_markup=admin_keyboard()
                )
                await state.clear()
                return

            await session.commit()

            # Уведомляем пользователя
            try:
                await message.bot.send_message(
                    user_id,
                    f"🎁 <b>Подарок от администрации!</b>\n\n"
                    f"Тебе добавлено <b>{days} дн.</b> к подписке.\n"
                    f"Спасибо что пользуешься нашим сервисом!",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"[Admin] Не удалось уведомить пользователя {user_id}: {e}")

            await message.answer(
                f"✅ <b>Подписка продлена</b>\n\n"
                f"Пользователь: <code>{user_id}</code>\n"
                f"Добавлено дней: <b>{days}</b>\n"
                f"Уведомление отправлено пользователю.",
                parse_mode="HTML",
                reply_markup=admin_keyboard()
            )
        else:
            # Клиента нет в панели - создаем нового
            print(f"[Admin] Создаем нового клиента для user_id={user_id} на {days} дней")
            vpn_client = await xray.create_client(user_id, days)

            if vpn_client:
                if sub:
                    # Обновляем существующую запись
                    print(f"[Admin] Обновляем существующую запись в БД")
                    sub.xray_uuid = vpn_client["uuid"]
                    sub.vless_link = vpn_client["vless_link"]
                    sub.expires_at = datetime.now(timezone.utc) + timedelta(days=days)
                    sub.is_active = True
                else:
                    # Создаем новую запись
                    print(f"[Admin] Создаем новую запись в БД")
                    sub = Subscription(
                        user_id=user_id,
                        xray_uuid=vpn_client["uuid"],
                        vless_link=vpn_client["vless_link"],
                        plan_key="admin",
                        expires_at=datetime.now(timezone.utc) + timedelta(days=days),
                        is_active=True
                    )
                    session.add(sub)

                await session.commit()

                # Уведомляем пользователя
                try:
                    await message.bot.send_message(
                        user_id,
                        f"🎁 <b>Подарок от администрации!</b>\n\n"
                        f"Тебе выдана подписка на <b>{days} дн.</b>\n"
                        f"Нажми «Мои ключи VPN» чтобы получить ключ для подключения.\n\n"
                        f"Спасибо что пользуешься нашим сервисом!",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    print(f"[Admin] Не удалось уведомить пользователя {user_id}: {e}")

                await message.answer(
                    f"✅ <b>Подписка создана</b>\n\n"
                    f"Пользователь: <code>{user_id}</code>\n"
                    f"Выдано дней: <b>{days}</b>\n"
                    f"Уведомление отправлено пользователю.",
                    parse_mode="HTML",
                    reply_markup=admin_keyboard()
                )
            else:
                await message.answer(
                    f"❌ Не удалось создать VPN клиента для пользователя <code>{user_id}</code>.\n"
                    f"Проверь логи панели 3X-UI.",
                    parse_mode="HTML",
                    reply_markup=admin_keyboard()
                )

    await state.clear()


@router.callback_query(F.data.startswith("admin_reset_trial:"))
async def admin_reset_trial(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    user_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if user:
            user.trial_used = False
            await session.commit()
            
            # Уведомляем пользователя
            try:
                await callback.bot.send_message(
                    user_id,
                    f"🎁 <b>Хорошие новости!</b>\n\n"
                    f"Тебе снова доступен пробный период!\n"
                    f"Используй команду /start чтобы активировать.",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"[Admin] Не удалось уведомить пользователя {user_id}: {e}")
            
            await callback.message.edit_text(
                f"✅ <b>Триал сброшен</b>\n\n"
                f"Пользователь <code>{user_id}</code> может снова использовать пробный период.\n"
                f"Уведомление отправлено пользователю.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Админ-панель", callback_data="back_admin")]
                ])
            )
        else:
            await callback.answer("Пользователь не найден", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ban:"))
async def admin_ban(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    user_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if user:
            user.is_banned = True
            await session.commit()
            
            # Уведомляем пользователя
            try:
                await callback.bot.send_message(
                    user_id,
                    f"🚫 <b>Доступ к боту ограничен</b>\n\n"
                    f"Ваш аккаунт был заблокирован администрацией.\n"
                    f"Для уточнения причин свяжитесь с поддержкой.",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"[Admin] Не удалось уведомить пользователя {user_id}: {e}")
            
            await callback.message.edit_text(
                f"🚫 <b>Пользователь забанен</b>\n\n"
                f"ID: <code>{user_id}</code>\n"
                f"Пользователь больше не сможет использовать бота.\n"
                f"Уведомление отправлено пользователю.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Админ-панель", callback_data="back_admin")]
                ])
            )
        else:
            await callback.answer("Пользователь не найден", show_alert=True)
    
    await callback.answer()


@router.callback_query(F.data.startswith("admin_unban:"))
async def admin_unban(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    
    user_id = int(callback.data.split(":")[1])
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if user:
            user.is_banned = False
            await session.commit()
            
            # Уведомляем пользователя
            try:
                await callback.bot.send_message(
                    user_id,
                    f"✅ <b>Доступ восстановлен</b>\n\n"
                    f"Ваш аккаунт был разблокирован.\n"
                    f"Теперь вы снова можете пользоваться ботом!",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"[Admin] Не удалось уведомить пользователя {user_id}: {e}")
            
            await callback.message.edit_text(
                f"✅ <b>Пользователь разбанен</b>\n\n"
                f"ID: <code>{user_id}</code>\n"
                f"Пользователь снова может использовать бота.\n"
                f"Уведомление отправлено пользователю.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Админ-панель", callback_data="back_admin")]
                ])
            )
        else:
            await callback.answer("Пользователь не найден", show_alert=True)
    
    await callback.answer()
