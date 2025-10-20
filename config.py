# config.py
# Файл конфигурации для API ключей

# Telegram Bot Token - получить от @BotFather
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"

# Aviasales API Token - получить на https://support.travelpayouts.com/
AVIASALES_API_TOKEN = "YOUR_AVIASALES_API_TOKEN_HERE"

# URL для Aviasales API
AVIASALES_API_BASE_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

# Настройки по умолчанию
DEFAULT_CURRENCY = "RUB"
DEFAULT_DAYS_AHEAD = 30
DEFAULT_PRICE_THRESHOLD = 10000

# Интервал проверки цен (в секундах)
CHECK_INTERVAL = 3600  # 1 час
