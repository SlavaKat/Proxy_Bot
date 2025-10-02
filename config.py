import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройки из .env
API_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
DB_FILE = os.getenv("DB_FILE", "proxy_bot.db")
PROXY_FOLDER = os.getenv("PROXY_FOLDER", "proxies")
MAX_TICKETS_PER_USER = int(os.getenv("MAX_TICKETS_PER_USER", "5"))
MEDIA_FOLDER = os.getenv("MEDIA_FOLDER", "support_media")
LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")
MAX_FEEDBACK_LENGTH = int(os.getenv("MAX_FEEDBACK_LENGTH", "4000"))

# Проверка обязательных переменных
if not API_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables!")

if not ADMIN_CHAT_ID:
    raise ValueError("ADMIN_CHAT_ID not found in environment variables!")

try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
    ADMIN_IDS = [ADMIN_CHAT_ID]  # Используем тот же ID для списка администраторов
except ValueError:
    raise ValueError("ADMIN_CHAT_ID must be an integer!")

# SQLAlchemy database URL
DATABASE_URL = f'sqlite:///{DB_FILE}'
