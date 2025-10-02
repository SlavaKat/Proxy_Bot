import os
import datetime
import logging
from aiogram import types, Bot
from database import add_proxy_file, load_proxy_files
from config import MEDIA_FOLDER, PROXY_FOLDER

# Сохранение медиафайла
async def save_media(media: types.PhotoSize | types.Video | types.Document, user_id: int, bot: Bot):
    os.makedirs(MEDIA_FOLDER, exist_ok=True)
    
    if isinstance(media, types.PhotoSize):
        file_ext = ".jpg"
        media_type = "photo"
        max_size = 10 * 1024 * 1024  # 10 MB для фото
    elif isinstance(media, types.Video):
        file_ext = ".mp4"
        media_type = "video"
        max_size = 20 * 1024 * 1024  # 20 MB для видео (ограничение Telegram)
    elif isinstance(media, types.Document):
        file_ext = os.path.splitext(media.file_name)[1] if media.file_name else ".bin"
        media_type = "document"
        max_size = 20 * 1024 * 1024  # 20 MB для документов (ограничение Telegram)
    else:
        return None, None
    
    # Проверяем размер файла
    if hasattr(media, 'file_size') and media.file_size > max_size:
        logging.warning(f"Файл слишком большой: {media.file_size} байт")
        return "too_big", None
    
    # Генерируем уникальное имя файла
    file_name = f"{user_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{file_ext}"
    file_path = os.path.join(MEDIA_FOLDER, file_name)
    
    # Скачиваем файл
    try:
        file = await bot.get_file(media.file_id)
        await bot.download_file(file.file_path, destination=file_path)
        return media_type, file_path
    except Exception as e:
        # Проверяем, является ли ошибка связанной с размером файла
        if "too big" in str(e).lower() or "file is too big" in str(e).lower():
            logging.warning(f"Файл слишком большой для Telegram: {e}")
            return "too_big", None
        logging.error(f"Ошибка при сохранении медиафайла: {e}")
        return None, None

# Функция для форматирования даты
def format_date(date_value):
    if isinstance(date_value, str):
        try:
            return datetime.datetime.strptime(date_value, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return date_value
    elif isinstance(date_value, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(date_value).strftime("%d.%m.%Y %H:%M")
        except (ValueError, OSError):
            return str(date_value)
    else:
        return str(date_value)

# Инициализация прокси-файлов
def init_proxy_files():
    # Создаем папки
    os.makedirs(PROXY_FOLDER, exist_ok=True)
    os.makedirs(MEDIA_FOLDER, exist_ok=True)
    
    # Создаем базовые файлы, если их нет
    base_files = {
        "proxy.txt": {"display": "Прокси", "description": "Обычные прокси"},
        "proxy+.txt": {"display": "Прокси+", "description": "Премиум прокси"}
    }
    
    # Получаем список существующих файлов из базы данных
    try:
        existing_files = [f['name'] for f in load_proxy_files()]
    except Exception as e:
        logging.error(f"Ошибка при загрузке списка прокси-файлов: {e}")
        existing_files = []
    
    for file_name, file_info in base_files.items():
        file_path = os.path.join(PROXY_FOLDER, file_name)
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                f.write("# Добавьте прокси в этот файл\n")
        
        # Добавляем файл в базу данных, если его там еще нет
        if file_name not in existing_files:
            try:
                add_proxy_file(
                    file_name=file_name,
                    display_name=file_info["display"],
                    description=file_info["description"]
                )
                logging.info(f"Добавлен прокси-файл в базу данных: {file_name}")
            except Exception as e:
                logging.error(f"Ошибка при добавлении прокси-файла {file_name}: {e}")