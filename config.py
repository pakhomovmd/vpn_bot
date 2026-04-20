from dotenv import load_dotenv
import os

load_dotenv()

# Telegram
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID: str = os.getenv("CHANNEL_ID", "")  # ID канала для обязательной подписки (например: @your_channel или -1001234567890)
CHANNEL_URL: str = os.getenv("CHANNEL_URL", "")  # Ссылка на канал для пользователей

# База данных
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# ЮKassa
YUKASSA_SHOP_ID: str = os.getenv("YUKASSA_SHOP_ID", "")
YUKASSA_SECRET_KEY: str = os.getenv("YUKASSA_SECRET_KEY", "")

# Cryptobot
CRYPTOBOT_TOKEN: str = os.getenv("CRYPTOBOT_TOKEN", "")

# Heleket
HELEKET_MERCHANT_ID: str = os.getenv("HELEKET_MERCHANT_ID", "")
HELEKET_API_KEY: str = os.getenv("HELEKET_API_KEY", "")

# Card Link
CARDLINK_API_TOKEN: str = os.getenv("CARDLINK_API_TOKEN", "")
CARDLINK_SHOP_ID: str = os.getenv("CARDLINK_SHOP_ID", "")

# 3X-UI / Xray
XRAY_PANEL_URL: str = os.getenv("XRAY_PANEL_URL", "")
XRAY_USERNAME: str = os.getenv("XRAY_USERNAME", "admin")
XRAY_PASSWORD: str = os.getenv("XRAY_PASSWORD", "")
XRAY_INBOUND_ID: int = int(os.getenv("XRAY_INBOUND_ID", "1"))  # ID входящего подключения в панели

# Настройки подписок
TRIAL_DAYS: int = int(os.getenv("TRIAL_DAYS", "5"))
REFERRAL_BONUS_DAYS: int = int(os.getenv("REFERRAL_BONUS_DAYS", "3"))
MAX_DEVICES: int = int(os.getenv("MAX_DEVICES", "3"))  # Максимальное количество устройств на пользователя

# Тарифы (в рублях)
PLANS: dict = {
    "1m": {"title": "1 месяц", "days": 30,  "price_rub": 199, "price_usd": 3, "price_stars": 150},
    "3m": {"title": "3 месяца", "days": 90,  "price_rub": 499, "price_usd": 8, "price_stars": 350},
    "6m": {"title": "6 месяцев", "days": 180, "price_rub": 899, "price_usd": 15, "price_stars": 650},
    "12m": {"title": "12 месяцев", "days": 365, "price_rub": 1999, "price_usd": 30, "price_stars": 1400},
}
