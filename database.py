import sqlite3
import datetime
import logging
import os
import json
from typing import List, Dict, Any, Optional, Tuple
from config import DB_FILE, PROXY_FOLDER, MAX_TICKETS_PER_USER

def get_connection() -> sqlite3.Connection:
    """Создает и возвращает соединение с базой данных"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Для доступа к полям по имени
    return conn

def init_db():
    """Инициализация базы данных и создание таблиц, если они не существуют"""
    try:
        with get_connection() as conn:
            c = conn.cursor()
            
            # Таблица прокси-файлов
            c.execute('''CREATE TABLE IF NOT EXISTS proxy_files (
                        file_name TEXT PRIMARY KEY,
                        display_name TEXT NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            
            # Таблица пользователей
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            
            # Таблица истории прокси
            c.execute('''CREATE TABLE IF NOT EXISTS proxy_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        proxy TEXT,
                        proxy_type TEXT,
                        issue_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES users(user_id))''')
            
            # Таблица настроек пользователя
            c.execute('''CREATE TABLE IF NOT EXISTS user_settings (
                        user_id INTEGER PRIMARY KEY,
                        language TEXT DEFAULT 'ru',
                        notifications INTEGER DEFAULT 1,
                        last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES users(user_id))''')
            
            # Таблица тикетов поддержки
            c.execute('''CREATE TABLE IF NOT EXISTS support_tickets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        message TEXT,
                        media_type TEXT,
                        media_path TEXT,
                        status TEXT DEFAULT 'open',
                        admin_id INTEGER,
                        reply_message TEXT,
                        reply_media_type TEXT,
                        reply_media_path TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        replied_at TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES users(user_id))''')
            
            # Таблица сообщений поддержки
            c.execute('''CREATE TABLE IF NOT EXISTS support_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ticket_id INTEGER,
                        user_id INTEGER,
                        message_text TEXT,
                        is_from_admin BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(ticket_id) REFERENCES support_tickets(id),
                        FOREIGN KEY(user_id) REFERENCES users(user_id))''')
            
            # Создаем папку для прокси, если её нет
            os.makedirs(PROXY_FOLDER, exist_ok=True)
            
            # Таблица для хранения информации о прокси-файлах
            c.execute('''CREATE TABLE IF NOT EXISTS proxy_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_name TEXT UNIQUE NOT NULL,
                        display_name TEXT NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
            
            # Таблица для хранения индекса текущего прокси
            c.execute('''CREATE TABLE IF NOT EXISTS proxy_index (
                        file_name TEXT PRIMARY KEY,
                        last_index INTEGER DEFAULT 0)''')
            
            # Таблица для хранения использованных прокси
            c.execute('''CREATE TABLE IF NOT EXISTS used_proxies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        proxy TEXT NOT NULL,
                        proxy_type TEXT NOT NULL,
                        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(proxy, proxy_type))''')
            
            # Таблица для отслеживания скачиваний прокси-файлов
            c.execute('''CREATE TABLE IF NOT EXISTS proxy_downloads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        file_name TEXT NOT NULL,
                        download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES users(user_id))''')
            
            # Создаем записи для существующих прокси-файлов, если их нет
            c.execute("SELECT file_name FROM proxy_files")
            for (file_name,) in c.fetchall():
                c.execute('''INSERT OR IGNORE INTO proxy_index (file_name, last_index) 
                            VALUES (?, 0)''', (file_name,))
            
            conn.commit()
            
    except Exception as e:
        logging.error(f"Ошибка при инициализации базы данных: {e}")
        raise

def migrate_db():
    """Миграция базы данных при обновлении структуры"""
    try:
        with get_connection() as conn:
            c = conn.cursor()
            
            # Создаем таблицу для индексации прокси, если её нет
            c.execute('''CREATE TABLE IF NOT EXISTS proxy_index (
                        file_name TEXT PRIMARY KEY,
                        last_index INTEGER DEFAULT 0)''')
            logging.info("Проверена/создана таблица proxy_index")
            
            # Проверяем наличие таблицы user_settings
            c.execute("""SELECT name FROM sqlite_master 
                        WHERE type='table' AND name='user_settings'""")
            table_exists = c.fetchone() is not None
            
            if table_exists:
                # Проверяем наличие колонок в таблице user_settings
                c.execute("PRAGMA table_info(user_settings)")
                columns = [column[1] for column in c.fetchall()]
                
                # Список колонок для добавления
                columns_to_add = [
                    ('language', 'TEXT', "DEFAULT 'ru'"),
                    ('notifications', 'INTEGER', 'DEFAULT 1'),
                    ('last_update', 'TIMESTAMP', 'DEFAULT CURRENT_TIMESTAMP')
                ]
                
                for column_name, column_type, default_value in columns_to_add:
                    if column_name not in columns:
                        try:
                            c.execute(f'''ALTER TABLE user_settings 
                                        ADD COLUMN {column_name} {column_type} {default_value}''')
                            logging.info(f"Добавлена колонка '{column_name}' в таблицу user_settings")
                        except sqlite3.Error as e:
                            logging.error(f"Ошибка при добавлении колонки '{column_name}': {e}")
            
            # Проверяем и обновляем таблицу support_tickets
            c.execute("PRAGMA table_info(support_tickets)")
            ticket_columns = [column[1] for column in c.fetchall()]
            
            # Список колонок для добавления в support_tickets
            ticket_columns_to_add = [
                ('username', 'TEXT'),
                ('first_name', 'TEXT'),
                ('last_name', 'TEXT'),
                ('message', 'TEXT'),
                ('media_type', 'TEXT'),
                ('media_path', 'TEXT'),
                ('status', 'TEXT', "DEFAULT 'open'"),
                ('admin_id', 'INTEGER'),
                ('reply_message', 'TEXT'),
                ('reply_media_type', 'TEXT'),
                ('reply_media_path', 'TEXT'),
                ('replied_at', 'TIMESTAMP')
            ]
            
            for column_info in ticket_columns_to_add:
                column_name = column_info[0]
                if column_name not in ticket_columns:
                    try:
                        if len(column_info) == 3:
                            # Если есть значение по умолчанию
                            c.execute(f'''ALTER TABLE support_tickets 
                                        ADD COLUMN {column_name} {column_info[1]} {column_info[2]}''')
                        else:
                            c.execute(f'''ALTER TABLE support_tickets 
                                        ADD COLUMN {column_name} {column_info[1]}''')
                        logging.info(f"Добавлена колонка '{column_name}' в таблицу support_tickets")
                    except sqlite3.Error as e:
                        logging.error(f"Ошибка при добавлении колонки '{column_name}': {e}")
            
            conn.commit()
            logging.info("Миграция базы данных выполнена успешно")
            
    except Exception as e:
        logging.error(f"Ошибка при миграции базы данных: {e}")
        raise

# Сохранение тикета в БД
def create_support_ticket(user_id, username, first_name, last_name, message, media_type=None, media_path=None):
    with get_connection() as conn:
        c = conn.cursor()
        
        # Проверяем лимит открытых тикетов
        c.execute("SELECT COUNT(*) FROM support_tickets WHERE user_id = ? AND status = 'open'", (user_id,))
        open_tickets = c.fetchone()[0]
        
        if open_tickets >= MAX_TICKETS_PER_USER:
            return None
        
        c.execute('''INSERT INTO support_tickets 
                     (user_id, username, first_name, last_name, message, media_type, media_path) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, username, first_name, last_name, message, media_type, media_path))
        
        ticket_id = c.lastrowid
        return ticket_id

# Обновление ответа на тикет
def update_ticket_reply(ticket_id, admin_id, reply_message, reply_media_type=None, reply_media_path=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''UPDATE support_tickets 
                 SET status = 'closed',
                     replied_at = CURRENT_TIMESTAMP,
                     admin_id = ?,
                     reply_message = ?,
                     reply_media_type = ?,
                     reply_media_path = ?
                 WHERE id = ?''',
              (admin_id, reply_message, reply_media_type, reply_media_path, ticket_id))
    
    conn.commit()
    conn.close()

# Получение открытых тикетов
def get_open_tickets():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT * FROM support_tickets WHERE status = 'open'")
    tickets = c.fetchall()
    conn.close()
    return tickets

# Получение тикетов пользователя
def get_user_tickets(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT * FROM support_tickets WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    tickets = c.fetchall()
    conn.close()
    return tickets

# Получение информации о тикете
def get_ticket_info(ticket_id):
    """Получение информации о тикете по ID"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM support_tickets WHERE id = ?",
            (ticket_id,)
        )
        return cursor.fetchone()

def update_ticket_status(ticket_id: int, status: str) -> bool:
    """Обновление статуса тикета
    
    Args:
        ticket_id: ID тикета
        status: Новый статус (open, closed, pending, etc.)
        
    Returns:
        bool: True если обновление прошло успешно, иначе False
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE support_tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, ticket_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Ошибка при обновлении статуса тикета {ticket_id}: {e}")
        return False

# Загрузка списка прокси-файлов
def load_proxy_files():
    """Load all proxy files from the database.
    
    Returns:
        list: List of dictionaries containing proxy file info, or empty list if none found
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT file_name, display_name, description FROM proxy_files")
        files = c.fetchall()
        return [{"name": f[0], "display": f[1], "description": f[2]} for f in files]
    except sqlite3.Error as e:
        logging.error(f"Error loading proxy files: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

# Добавление нового прокси-файла
def add_proxy_file(file_name, display_name, description=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO proxy_files (file_name, display_name, description) VALUES (?, ?, ?)",
                  (file_name, display_name, description))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# Загрузка прокси из файла
def load_proxies(file_name):
    file_path = os.path.join(PROXY_FOLDER, file_name)
    try:
        with open(file_path, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []

# Получение следующего прокси из файла
def get_next_proxy(file_name):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Получаем все прокси из файла
    all_proxies = load_proxies(file_name)
    if not all_proxies:
        return None
    
    # Получаем текущий индекс
    c.execute("SELECT last_index FROM proxy_index WHERE file_name = ?", (file_name,))
    result = c.fetchone()
    current_index = result[0] if result else 0
    
    # Выбираем следующий прокси
    next_index = (current_index + 1) % len(all_proxies)
    proxy = all_proxies[next_index]
    
    # Обновляем индекс
    c.execute('''INSERT OR REPLACE INTO proxy_index (file_name, last_index)
                 VALUES (?, ?)''', (file_name, next_index))
    
    conn.commit()
    conn.close()
    return proxy

# Помечаем прокси как использованный
def mark_proxy_as_used(proxy, proxy_type):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        c.execute("INSERT INTO used_proxies (proxy, proxy_type) VALUES (?, ?)", (proxy, proxy_type))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Прокси уже помечен как использованный
        return False
    finally:
        conn.close()

# Сохранение истории прокси
def save_proxy_history(user_id, proxy, proxy_type):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    c.execute("INSERT INTO proxy_history (user_id, proxy, proxy_type) VALUES (?, ?, ?)", 
              (user_id, proxy, proxy_type))
    conn.commit()
    conn.close()

# Получение истории прокси
def get_proxy_history(user_id, limit=10):
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''
            SELECT id, proxy, proxy_type, datetime(issue_date, 'localtime') as issue_date
            FROM proxy_history
            WHERE user_id = ?
            ORDER BY issue_date DESC
            LIMIT ?
        ''', (user_id, limit))
        return [dict(row) for row in c.fetchall()]

def log_proxy_download(user_id: int, file_name: str) -> None:
    with get_connection() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO proxy_downloads (user_id, file_name)
            VALUES (?, ?)
        ''', (user_id, file_name))
        conn.commit()

def get_proxy_downloads(limit: int = 50) -> list[dict]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('''
            SELECT d.id, d.user_id, d.file_name, 
                   datetime(d.download_time, 'localtime') as download_time,
                   u.username, u.first_name, u.last_name
            FROM proxy_downloads d
            LEFT JOIN users u ON d.user_id = u.user_id
            ORDER BY d.download_time DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in c.fetchall()]

def get_user_proxy_downloads(user_id: int, limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('''
            SELECT id, file_name, datetime(download_time, 'localtime') as download_time
            FROM proxy_downloads
            WHERE user_id = ?
            ORDER BY download_time DESC
            LIMIT ?
        ''', (user_id, limit))
        return [dict(row) for row in c.fetchall()]

# Получение настроек пользователя
def get_user_settings(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    settings = c.fetchone()
    if not settings:
        c.execute('''INSERT INTO user_settings (user_id) VALUES (?)''', (user_id,))
        conn.commit()
        settings = (user_id, 'ru', 1)
    conn.close()
    return {
        'user_id': settings[0],
        'language': settings[1],
        'notifications': settings[2]
    }