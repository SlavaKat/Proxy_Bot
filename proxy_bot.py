import sys
import os
import logging
import asyncio
import signal
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

# Добавляем текущую директорию в путь поиска модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import API_TOKEN
from database import init_db, migrate_db
from handlers import setup_handlers
from utils import init_proxy_files

# Инициализация хранилища состояний
storage = MemoryStorage()

# Обработчик сигналов для graceful shutdown
def handle_signal():
    logging.info("Получен сигнал завершения работы")
    loop = asyncio.get_event_loop()
    loop.create_task(shutdown())

async def shutdown():
    logging.info("Бот завершает работу...")

async def set_main_menu(bot: Bot):
    # Создаем список с командами и их описанием
    main_menu_commands = [
        BotCommand(command='/start',
                   description='Запустить бота'),
    ]
    await bot.set_my_commands(main_menu_commands)

# Запуск бота
async def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Инициализация базы данных и файлов прокси
    init_db()
    migrate_db()
    init_proxy_files()
    
    # Проверка доступности прокси-файлов
    from database import load_proxy_files
    proxy_files = load_proxy_files()
    logging.info(f"Загружено {len(proxy_files)} файлов прокси")
    
    # Проверка администратора
    from config import ADMIN_CHAT_ID
    logging.info(f"ID администратора: {ADMIN_CHAT_ID}")
    
    # Инициализация бота и диспетчера
    bot = Bot(
        token=API_TOKEN, 
        parse_mode=ParseMode.HTML
    )
    dp = Dispatcher(storage=storage)
    
    # Устанавливаем главное меню команд
    await set_main_menu(bot)
    
    # Настройка обработчиков
    setup_handlers(dp)
    
    # Настройка обработчиков сигналов
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal)
    
    try:
        # Настройка таймаута через aiohttp-сессию
        session = bot.session
        session.timeout = 60.0  # 60 секунд таймаут
        
        logging.info("Запуск бота...")
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        raise
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())