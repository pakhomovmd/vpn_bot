# 🌸 Sakura VPN Bot

Полнофункциональный Telegram бот для автоматизации продажи VPN подписок с интеграцией 3X-UI панели (Xray) и множественными платежными системами.

## 🚀 Возможности

### Основной функционал
- **Автоматическая регистрация** с выдачей пробного периода (5 дней)
- **Реферальная программа** - +3 дня VPN за каждого приглашенного друга
- **4 способа оплаты**: Telegram Stars, банковские карты, CryptoBot, любая криптовалюта
- **Автоматическое управление VPN** через 3X-UI API
- **Обязательная подписка на канал** с проверкой через middleware
- **Ограничение на 3 устройства** на пользователя

### Платежные системы
- 💳 **Банковские карты** (Card Link API) - российские карты
- ⭐ **Telegram Stars** - встроенная оплата Telegram
- 🤖 **CryptoBot** - TON, USDT, BTC, USDC, TRX
- 💎 **Heleket** - любая криптовалюта и сеть

### Личный кабинет
- Просмотр активной подписки и времени до истечения
- Получение VPN ключей (VLESS ссылки)
- Инструкции по подключению для iOS/Android/Windows/Mac
- Статистика рефералов и бонусов

### Админ-панель
- Статистика: пользователи, подписки, доход
- Поиск пользователя по ID
- Выдача бонусных дней
- Сброс триала
- Бан/разбан пользователей
- Массовая рассылка

### Автоматизация
- **Ежедневно в 10:00** - уведомления об истечении подписки (за 3 дня)
- **Каждый час** - автоматическая деактивация истекших подписок

## 🛠 Технологический стек

- **Python 3.11+**
- **aiogram 3.13** - асинхронный Telegram Bot API
- **PostgreSQL** + SQLAlchemy 2.0 (async ORM)
- **3X-UI** (Xray-core) - VPN панель
- **APScheduler** - планировщик задач
- **aiohttp** - HTTP клиент

## 📦 Установка

### 1. Клонируй репозиторий

```bash
git clone https://github.com/pakhomovmd/vpn_bot.git
cd vpn_bot
```

### 2. Создай виртуальное окружение

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

### 3. Установи зависимости

```bash
pip install -r requirements.txt
```

### 4. Настрой базу данных

Установи PostgreSQL и создай базу данных:

```sql
CREATE DATABASE vpn_bot;
CREATE USER vpn_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE vpn_bot TO vpn_user;
```

### 5. Настрой .env файл

Скопируй `.env.example` в `.env` и заполни своими данными:

```bash
cp .env.example .env
```

**Обязательные параметры:**
```env
# Telegram
BOT_TOKEN=your_bot_token_from_@BotFather
ADMIN_ID=your_telegram_id

# База данных
DATABASE_URL=postgresql+asyncpg://vpn_user:password@localhost:5432/vpn_bot

# 3X-UI панель
XRAY_PANEL_URL=https://your_server_ip:2053
XRAY_USERNAME=admin
XRAY_PASSWORD=your_password
XRAY_INBOUND_ID=1
```

**Опциональные параметры:**
```env
# Подписка на канал
CHANNEL_ID=@your_channel_username
CHANNEL_URL=https://t.me/your_channel

# Платежные системы (настрой хотя бы одну)
CRYPTOBOT_TOKEN=your_token
HELEKET_MERCHANT_ID=your_id
HELEKET_API_KEY=your_key
CARDLINK_API_TOKEN=your_token
CARDLINK_SHOP_ID=your_shop_id

# Настройки
TRIAL_DAYS=5
REFERRAL_BONUS_DAYS=3
MAX_DEVICES=3
```

### 6. Запусти бота

```bash
python bot.py
```

## 🔧 Настройка 3X-UI панели

### Установка 3X-UI

```bash
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)
```

### Настройка безопасности

1. **Измени порт панели** (по умолчанию 2053):
   - Зайди в Panel Settings → Port
   - Установи случайный порт (например, 18472)

2. **Настрой WebBasePath**:
   - Panel Settings → Web Base Path
   - Установи уникальный путь (например, `/secret-path-x7k9m2/`)

3. **Обнови .env**:
```env
XRAY_PANEL_URL=https://your_server_ip:18472
XRAY_PANEL_PATH=secret-path-x7k9m2
```

### Создание Inbound

1. Зайди в 3X-UI панель
2. Создай новый Inbound с протоколом VLESS + Reality
3. Запомни ID inbound (обычно 1)
4. Укажи его в `.env` как `XRAY_INBOUND_ID`

## 📱 Настройка подписки на канал

### 1. Создай канал в Telegram

### 2. Добавь бота в канал как администратора

### 3. Получи ID канала

**Для публичного канала:**
```
@your_channel_username
```

**Для приватного канала:**
1. Перешли сообщение из канала боту @userinfobot
2. Скопируй ID (например: `-1001234567890`)

### 4. Обнови .env

```env
CHANNEL_ID=@your_channel_username
CHANNEL_URL=https://t.me/your_channel
```

## 📊 Структура проекта

```
vpn_bot/
├── bot.py              # Точка входа
├── config.py           # Конфигурация
├── database/           # Модели БД
│   ├── models.py       # User, Subscription, Payment, ReferralBonus
│   └── db.py           # Async engine
├── handlers/           # Обработчики
│   ├── start.py        # Регистрация, триал, рефералы
│   ├── cabinet.py      # Личный кабинет
│   ├── payment.py      # Платежная система
│   ├── admin.py        # Админ-панель
│   └── subscription.py # Проверка подписки
├── services/           # Внешние API
│   ├── vpn.py          # 3X-UI API
│   ├── cryptopay.py    # CryptoBot
│   ├── heleket.py      # Heleket
│   ├── cardlink.py     # Card Link
│   └── scheduler.py    # Планировщик
├── middlewares/        # Middleware
│   └── subscription_check.py
└── keyboards/          # Клавиатуры
    └── inline.py
```

## 🗄 База данных

### Таблицы

- **users** - пользователи, рефералы, баланс
- **subscriptions** - VPN подписки с UUID и VLESS ссылками
- **payments** - история платежей
- **referral_bonuses** - реферальные бонусы

## 🔐 Безопасность

- `.env` файл исключен из git
- Cookie-based авторизация в 3X-UI
- MD5 подписи для платежных API
- Проверка ADMIN_ID для админских команд

## 📝 Тарифы

По умолчанию настроены следующие тарифы:

| Период | Цена (₽) | Цена ($) | Цена (⭐) |
|--------|----------|----------|-----------|
| 1 месяц | 199 | 3 | 150 |
| 3 месяца | 499 | 8 | 350 |
| 6 месяцев | 899 | 15 | 650 |
| 12 месяцев | 1999 | 30 | 1400 |

Тарифы настраиваются в `config.py`.

## 🚀 Деплой на сервер

### Использование systemd

Создай файл `/etc/systemd/system/vpn_bot.service`:

```ini
[Unit]
Description=VPN Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/vpn_bot
Environment="PATH=/path/to/vpn_bot/venv/bin"
ExecStart=/path/to/vpn_bot/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Запусти сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable vpn_bot
sudo systemctl start vpn_bot
```

## 📖 Документация

Подробная документация по настройке доступна в файле [README_SETUP.md](README_SETUP.md).

## 🤝 Поддержка

Если возникли вопросы или проблемы:
- Создай Issue в GitHub
- Напиши в Telegram: @sakuravpn_supp

## 📄 Лицензия

MIT License

## 🙏 Благодарности

- [aiogram](https://github.com/aiogram/aiogram) - Telegram Bot framework
- [3X-UI](https://github.com/MHSanaei/3x-ui) - Xray panel
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM

---

Сделано с ❤️ для автоматизации VPN бизнеса
