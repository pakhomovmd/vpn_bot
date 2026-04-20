from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import PLANS


def main_menu() -> InlineKeyboardMarkup:
    from config import CHANNEL_URL
    buttons = [
        [InlineKeyboardButton(text="👤 Личный кабинет", callback_data="cabinet")],
        [InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy")],
        [InlineKeyboardButton(text="👥 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="🔑 Мои ключи VPN", callback_data="my_keys")],
        [InlineKeyboardButton(text="❓ Как подключиться", callback_data="how_to_connect")],
    ]
    if CHANNEL_URL:
        buttons.append([InlineKeyboardButton(text="📢 Наш канал", url=CHANNEL_URL)])
    buttons.append([InlineKeyboardButton(text="💬 Поддержка", callback_data="support")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def plans_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for key, plan in PLANS.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"{plan['title']} — {plan['price_rub']} ₽",
                callback_data=f"plan:{key}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_keyboard(payment_url: str, payment_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_payment:{payment_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main")],
    ])


def cabinet_keyboard(has_active_sub: bool) -> InlineKeyboardMarkup:
    buttons = []
    if has_active_sub:
        buttons.append([InlineKeyboardButton(text="🔑 Мои ключи VPN", callback_data="my_keys")])
        buttons.append([InlineKeyboardButton(text="⏳ Продлить подписку", callback_data="buy")])
    else:
        buttons.append([InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy")])
    buttons.append([InlineKeyboardButton(text="👥 Рефералы", callback_data="referral")])
    buttons.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_main")]
    ])


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👤 Найти пользователя", callback_data="admin_find_user")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
    ])
