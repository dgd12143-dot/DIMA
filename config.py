import os

# Получаем токены из переменных окружения (для безопасности)
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "ВАШ_КЛЮЧ_CLAUDE")

# Часовой пояс (Stockholm)
TIMEZONE = "Europe/Stockholm"
