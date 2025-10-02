import logging
import os
from aiogram import types, F, Bot, Router, Dispatcher
from aiogram.filters import Command, or_f
from aiogram.fsm.context import FSMContext
from aiogram.enums import ContentType
from database import (
    load_proxy_files, get_next_proxy, mark_proxy_as_used, save_proxy_history, 
    update_ticket_status, init_db, migrate_db, create_support_ticket, 
    get_proxy_history, get_user_settings, get_user_tickets, update_ticket_reply,
    get_ticket_info, get_user_proxy_downloads, log_proxy_download, get_proxy_downloads
)
from utils import init_proxy_files

# Create a router
router = Router()
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from config import (
    ADMIN_CHAT_ID, DB_FILE, MEDIA_FOLDER as SUPPORT_MEDIA_FOLDER,
    PROXY_FOLDER, MAX_TICKETS_PER_USER, ADMIN_IDS
)
import sqlite3
from datetime import datetime, timedelta
from keyboards import *
from states import SupportStates
from utils import save_media, format_date

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    init_db()
    migrate_db()
    init_proxy_files()
    await message.answer(
        "👋 Привет! Я бот для выдачи прокси.\n\n"
        "👇 Нажмите на кнопку 🆘 Поддержка. Напишите сообщение: \"Отправить инструкцию по подключению прокси\". Я вам отправлю эту инструкцию.\n\n"
        "👉 Дополнительная поддержка: @VyacheslavKatirkin \n\n"
        "👇 Используйте меню ниже для навигации:",
        reply_markup=get_main_menu()
    )

@router.message(F.text == "🍔 Получить прокси")
async def get_proxy_handler(message: types.Message):
    try:
        # Загружаем список прокси-файлов
        proxy_files = load_proxy_files()
        
        # Если список пуст, инициализируем файлы заново
        if not proxy_files:
            init_proxy_files()
            proxy_files = load_proxy_files()
            
            # Если после инициализации все еще пусто, выводим ошибку
            if not proxy_files:
                await message.answer("⚠️ Ошибка: не удалось загрузить список прокси. Пожалуйста, попробуйте позже или обратитесь к администратору.")
                return
        
        # Создаем список кнопок
        buttons = []
        for file in proxy_files:
            # Проверяем, что файл существует
            file_path = os.path.join("proxies", file['name'])
            if not os.path.exists(file_path):
                logging.warning(f"Файл прокси не найден: {file_path}")
                continue
                
            buttons.append(
                InlineKeyboardButton(
                    text=file['display'],
                    callback_data=f"getproxy_{file['name']}"
                )
            )
        
        # Если нет доступных прокси, выводим сообщение
        if not buttons:
            await message.answer("⚠️ В данный момент нет доступных прокси. Пожалуйста, попробуйте позже.")
            return
        
        # Группируем кнопки по 2 в ряд
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            buttons[i:i+2] for i in range(0, len(buttons), 2)
        ])
        
        # Удаляем предыдущее сообщение с кнопками, если оно есть
        try:
            await message.delete()
        except Exception as e:
            logging.warning(f"Не удалось удалить сообщение: {e}")
            # Продолжаем выполнение, даже если не удалось удалить сообщение
            
        # Отправляем новое сообщение с кнопками
        await message.answer(
            "🔍 Выберите тип прокси:",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logging.error(f"Ошибка при получении списка прокси: {e}")
        await message.answer("⚠️ Произошла ошибка при загрузке списка прокси. Пожалуйста, попробуйте позже или обратитесь к администратору.")

@router.callback_query(F.data.startswith("getproxy_"))
async def get_proxy_callback(callback: types.CallbackQuery):
    file_name = callback.data.split("_", 1)[1]
    
    # Получаем следующий прокси
    proxy = get_next_proxy(file_name)
    
    if not proxy:
        await callback.answer("⚠️ В этом файле закончились прокси!", show_alert=True)
        return
    
    # Помечаем прокси как использованный
    mark_proxy_as_used(proxy, file_name)
    
    # Сохраняем в историю
    display_name = next((f['display'] for f in load_proxy_files() if f['name'] == file_name), file_name)
    save_proxy_history(callback.from_user.id, proxy, display_name)
    
    await callback.message.edit_text(
        f"🔑 Ваш прокси ({display_name}):\n<code>{proxy}</code>\n\n"
        "✅ Сохраните его в безопасном месте!\n"
        "🔄 Для нового прокси нажмите кнопку ещё раз"
    )
    
    # Уведомление админу
    await callback.bot.send_message(
        ADMIN_CHAT_ID,
        f"🆕 Выдан прокси пользователю {callback.from_user.mention_html()}\n"
        f"ID: {callback.from_user.id}\n"
        f"Тип: {display_name}\n"
        f"Прокси: {proxy}"
    )

@router.message(F.text == "📥 Скачать файл")
async def download_file_handler(message: types.Message):
    proxy_files = load_proxy_files()
    if not proxy_files:
        await message.answer("⚠️ Нет доступных прокси-файлов. Обратитесь к администратору.")
        return
    
    # Создаем список кнопок
    buttons = []
    for file in proxy_files:
        # Создаем две кнопки для каждого файла: одна для скачивания, другая для получения имени файла
        buttons_row = [
            InlineKeyboardButton(
                text=f"📄 {file['display']}",
                callback_data=f"download_{file['name']}"
            ),
            InlineKeyboardButton(
                text="🔗 Ссылка",
                callback_data=f"link_{file['name']}"
            )
        ]
        buttons.append(buttons_row)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        "📥 Выберите файл для скачивания или получите ссылку на него:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("download_"))
async def download_file_callback(callback: types.CallbackQuery):
    file_name = callback.data.split("_", 1)[1]
    file_path = os.path.join(PROXY_FOLDER, file_name)
    
    if not os.path.exists(file_path):
        await callback.answer("❌ Файл не найден!", show_alert=True)
        return
    
    try:
        # Логируем скачивание
        log_proxy_download(callback.from_user.id, file_name)
        
        # Отправляем файл пользователю
        await callback.bot.send_document(
            callback.from_user.id,
            FSInputFile(file_path),
            caption=f"📥 <b>Файл:</b> {file_name}\n\n<i>Сохраните файл на свое устройство</i>"
        )
        await callback.answer("✅ Файл отправлен!")
        
        # Уведомляем администратора о скачивании
        if str(callback.from_user.id) != str(ADMIN_CHAT_ID):
            admin_message = (
                f"📥 Пользователь скачал прокси-файл\n"
                f"👤 Пользователь: {callback.from_user.mention_html()}\n"
                f"🆔 ID: {callback.from_user.id}\n"
                f"📂 Файл: {file_name}"
            )
            await callback.bot.send_message(
                ADMIN_CHAT_ID,
                admin_message,
                parse_mode='HTML'
            )
            
    except Exception as e:
        logging.error(f"Ошибка при отправке файла: {e}")
        await callback.answer("❌ Не удалось отправить файл!", show_alert=True)

@router.callback_query(F.data.startswith("link_"))
async def get_file_link_callback(callback: types.CallbackQuery):
    file_name = callback.data.split("_", 1)[1]
    file_path = os.path.join(PROXY_FOLDER, file_name)
    
    if not os.path.exists(file_path):
        await callback.answer("❌ Файл не найден!", show_alert=True)
        return
    
    # Отправляем пользователю сообщение с именем файла как "ссылкой" (пользователь может скопировать имя файла)
    await callback.message.answer(
        f"🔗 <b>Ссылка на файл:</b> <code>{file_name}</code>\n\n"
        f"Вы можете скопировать имя файла и использовать его по назначению."
    )
    await callback.answer("✅ Ссылка скопирована!")

@router.message(Command("downloads"))
async def cmd_downloads(message: types.Message):
    """Показать историю скачиваний (только для администратора)"""
    if str(message.from_user.id) != str(ADMIN_CHAT_ID):
        return
        
    downloads = get_proxy_downloads(limit=20)
    if not downloads:
        await message.answer("📭 Нет данных о скачиваниях")
        return
    
    response = "📥 <b>Последние скачивания прокси-файлов:</b>\n\n"
    for dl in downloads:
        user_info = f"{dl.get('first_name', '')} {dl.get('last_name', '')} (@{dl.get('username', '')})".strip()
        if not user_info.strip():
            user_info = f"ID: {dl['user_id']}"
            
        response += (
            f"👤 <b>{user_info}</b>\n"
            f"📂 Файл: {dl['file_name']}\n"
            f"🕒 {dl['download_time']}\n"
            "────────────────────\n"
        )
    
    await message.answer(response, parse_mode='HTML')

@router.message(Command("mydownloads"))
async def cmd_my_downloads(message: types.Message):
    """Показать историю моих скачиваний"""
    downloads = get_user_proxy_downloads(message.from_user.id)
    if not downloads:
        await message.answer("📭 Вы еще не скачивали прокси-файлы")
        return
    
    response = "📥 <b>Ваши последние скачивания:</b>\n\n"
    for dl in downloads:
        response += (
            f"📂 Файл: {dl['file_name']}\n"
            f"🕒 {dl['download_time']}\n"
            "────────────────────\n"
        )
    
    await message.answer(response, parse_mode='HTML')

@router.message(F.text == "📜 История")
async def history_handler(message: types.Message):
    # Получаем историю прокси и загрузок
    proxy_history = get_proxy_history(message.from_user.id)
    download_history = get_user_proxy_downloads(message.from_user.id, limit=10)
    
    if not proxy_history and not download_history:
        await message.answer("📭 У вас еще нет истории", 
                           reply_markup=get_main_menu())
        return
    
    response = "📜 <b>Ваша история:</b>\n\n"
    
    # История прокси
    if proxy_history:
        response += "<b>Выданные прокси:</b>\n"
        for item in proxy_history:
            proxy_type = item.get('proxy_type', 'Неизвестный тип')
            proxy = item.get('proxy', 'Нет данных')
            date = item.get('issue_date', 'Неизвестная дата')
            response += f"• <b>{proxy_type}</b>\n<code>{proxy}</code>\n└ {date}\n\n"
    
    # История загрузок
    if download_history:
        response += "\n<b>Скачанные файлы:</b>\n"
        for dl in download_history:
            file_name = dl.get('file_name', 'Неизвестный файл')
            dl_time = dl.get('download_time', 'Неизвестное время')
            response += f"• {file_name}\n└ {dl_time}\n"
    
    await message.answer(response, parse_mode='HTML')

@router.message(F.text == "📎 Мои файлы")
async def my_files_handler(message: types.Message):
    """Показать прикрепленные файлы пользователя"""
    user_id = message.from_user.id
    user_dir = os.path.join(SUPPORT_MEDIA_FOLDER, str(user_id))
    
    if not os.path.exists(user_dir) or not os.listdir(user_dir):
        await message.answer("📭 У вас пока нет прикрепленных файлов.")
        return
    
    files = [f for f in os.listdir(user_dir) if os.path.isfile(os.path.join(user_dir, f))]
    
    response = "📁 <b>Ваши прикрепленные файлы:</b>\n\n"
    for idx, file in enumerate(files, 1):
        file_path = os.path.join(user_dir, file)
        file_size = os.path.getsize(file_path) / 1024  # размер в КБ
        response += f"{idx}. {file} ({file_size:.1f} КБ)\n"
    
    response += "\n📌 Для загрузки файла просто отправьте его боту в чат поддержки."
    
    await message.answer(response, parse_mode='HTML')

@router.message(F.text == "📊 Статистика")
async def show_statistics(message: types.Message):
    # Проверяем, является ли пользователь администратором
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ У вас нет прав для просмотра статистики")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # Общая статистика
        c.execute("""
            SELECT
                (SELECT COUNT(*) FROM users) as total_users,
                (SELECT COUNT(*) FROM proxy_history) as total_proxies_issued,
                (SELECT COUNT(*) FROM proxy_downloads) as total_downloads,
                (SELECT COUNT(DISTINCT user_id) FROM proxy_downloads) as active_users
        """)
        stats = c.fetchone()

        # Статистика по дням
        week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        c.execute("""
            SELECT
                date(issue_date) as day,
                COUNT(*) as count
            FROM proxy_history
            WHERE date(issue_date) >= ?
            GROUP BY date(issue_date)
            ORDER BY day DESC
        """, (week_ago,))
        daily_stats = c.fetchall()

        # Популярные прокси
        c.execute("""
            SELECT
                proxy_type,
                COUNT(*) as count
            FROM proxy_history
            GROUP BY proxy_type
            ORDER BY count DESC
            LIMIT 5
        """)
        top_proxies = c.fetchall()

        # Активные пользователи
        c.execute("""
            SELECT
                u.user_id,
                u.first_name,
                u.username,
                COUNT(h.id) as proxy_count
            FROM users u
            LEFT JOIN proxy_history h ON u.user_id = h.user_id
            GROUP BY u.user_id
            ORDER BY proxy_count DESC
            LIMIT 5
        """)
        active_users = c.fetchall()

        # Формируем сообщение
        response = (
            "📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: <b>{stats[0]}</b>\n"
            f"🔑 Выдано прокси: <b>{stats[1]}</b>\n"
            f"📥 Всего загрузок: <b>{stats[2]}</b>\n"
            f"👥 Активных пользователей: <b>{stats[3]}</b>\n\n"
            "<b>📈 Активность за неделю:</b>\n"
        )

        # Добавляем статистику по дням
        for day, count in daily_stats:
            response += f"• {day}: <b>{count}</b> выдач прокси\n"

        # Добавляем топ прокси
        response += "\n<b>🔥 Популярные прокси:</b>\n"
        for proxy_type, count in top_proxies:
            response += f"• {proxy_type}: <b>{count}</b> выдач\n"

        # Добавляем активных пользователей
        response += "\n<b>👥 Самые активные пользователи:</b>\n"
        for user_id, first_name, username, count in active_users:
            username = f"@{username}" if username else "без username"
            response += f"• <a href='tg://user?id={user_id}'>{first_name}</a> ({username}): <b>{count}</b> прокси\n"

        await message.answer(response, parse_mode='HTML', disable_web_page_preview=True)

    except Exception as e:
        logging.error(f"Ошибка при получении статистики: {e}")
        await message.answer("❌ Произошла ошибка при загрузке статистики")

@router.message(F.text == "⚙️ Настройки")
async def settings_handler(message: types.Message):
    settings = get_user_settings(message.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌐 Сменить язык", callback_data="change_lang")
        ],
        [
            InlineKeyboardButton(
                text=f"🔔 Уведомления: {'Вкл' if settings['notifications'] else 'Выкл'}",
                callback_data="toggle_notify"
            )
        ]
    ])
    
    await message.answer(
        "⚙️ <b>Настройки профиля</b>\n\n"
        f"🌐 Язык: {settings['language'].upper()}\n"
        f"🔔 Уведомления: {'Включены' if settings['notifications'] else 'Выключены'}",
        reply_markup=keyboard
    )

@router.message(F.text == "🆘 Поддержка")
async def support_handler(message: types.Message, state: FSMContext):
    await message.answer(
        "🆘 <b>Служба поддержки</b>\n\n"
        "Вы можете:\n"
        "1. Отправить новое обращение (текст, фото или видео)\n"
        "2. Посмотреть истории ваших обращений\n\n"
        "Чтобы отправить новое обращение, просто напишите сообщение или прикрепите файл ниже.",
        reply_markup=get_support_menu()
    )
    await state.set_state(SupportStates.WAITING_MESSAGE)

@router.message(SupportStates.WAITING_MESSAGE, F.text == "✉️ Мои обращения")
async def my_tickets_handler(message: types.Message, state: FSMContext):
    tickets = get_user_tickets(message.from_user.id)
    
    if not tickets:
        await message.answer("📭 У вас еще нет обращений в поддержку", reply_markup=get_support_menu())
        return
    
    tickets_text = "📬 <b>Ваши обращения в поддержку:</b>\n\n"
    for ticket in tickets:
        status = "🟢 Открыт" if ticket[8] == 'open' else "🔴 Закрыт"
        date_str = format_date(ticket[9])
        
        # Добавляем информацию о медиа
        media_info = ""
        if ticket[6]:  # media_type
            media_icon = "🖼️" if ticket[6] == "photo" else "🎥" if ticket[6] == "video" else "📄"
            media_info = f"\n{media_icon} Прикреплен файл"
        
        # Добавляем информацию о медиа в ответе
        reply_media_info = ""
        if len(ticket) > 13 and ticket[13]:  # reply_media_type
            reply_media_icon = "🖼️" if ticket[13] == "photo" else "🎥" if ticket[13] == "video" else "📄"
            reply_media_info = f"\n{reply_media_icon} В ответе прикреплен файл"
        
        tickets_text += f"<b>#{ticket[0]}</b> - {status}{media_info}{reply_media_info}\nДата: {date_str}\n\n"
    
    await message.answer(tickets_text, reply_markup=get_support_menu())

@router.message(SupportStates.WAITING_MESSAGE, F.text == "❌ Отмена")
async def cancel_support_handler(message: types.Message, state: FSMContext):
    await message.answer("❌ Создание обращения отменено", reply_markup=get_main_menu())
    await state.clear()

async def process_support_message(message: types.Message, state: FSMContext):
    user = message.from_user
    media_type = None
    media_path = None
    ticket_text = ""
    
    # Определяем тип контента
    if message.text:
        ticket_text = message.text
    elif message.caption:
        ticket_text = message.caption
    
    # Обработка медиафайлов
    if message.photo:
        media = message.photo[-1]  # Берем фото с самым высоким разрешением
        media_type, media_path = await save_media(media, message.from_user.id, message.bot)
    elif message.video:
        media_type, media_path = await save_media(message.video, message.from_user.id, message.bot)
    elif message.document:
        media_type, media_path = await save_media(message.document, message.from_user.id, message.bot)
    
    # Обработка слишком больших файлов
    if media_type == "too_big":
        await message.answer("❌ Файл слишком большой. Максимальный размер файла — 20 МБ для видео и документов.")
        return
    
    # Если нет текста и нет медиа
    if not ticket_text and not media_type:
        await message.answer("❌ Сообщение не может быть пустым. Добавьте текст или файл.")
        return
    
    # Создаем тикет
    ticket_id = create_support_ticket(
        user.id,
        user.username,
        user.first_name,
        user.last_name,
        ticket_text,
        media_type,
        media_path
    )
    
    if not ticket_id:
        await message.answer(
            f"⚠️ У вас слишком много открытых обращений (максимум {MAX_TICKETS_PER_USER}).\n"
            "Закройте существующие обращения перед созданием нового.",
            reply_markup=get_main_menu()
        )
        await state.clear()
        return
    
    # Клавиатура для администратора
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✍️ Ответить", 
                callback_data=f"reply_ticket_{ticket_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="👤 Профиль пользователя", 
                url=f"tg://user?id={user.id}"
            )
        ]
    ])
    
    # Уведомление администратору
    try:
        if media_type and media_path and media_type != "too_big":
            # Формируем текст с информацией о медиа
            media_icon = "🖼️" if media_type == "photo" else "🎥" if media_type == "video" else "📄"
            caption = (
                f"🆘 <b>Новое обращение в поддержку!</b>\n\n"
                f"🔢 ID: <code>#{ticket_id}</code>\n"
                f"👤 Пользователь: {user.mention_html()}\n"
                f"🆔 ID: <code>{user.id}</code>\n\n"
                f"{media_icon} <b>Прикреплен файл</b>\n"
                f"📝 Сообщение:\n<code>{ticket_text}</code>"
            )
            
            # Проверяем существование файла перед отправкой
            if not os.path.exists(media_path):
                logging.error(f"Файл не найден: {media_path}")
                await message.bot.send_message(
                    ADMIN_CHAT_ID,
                    f"⚠️ <b>Ошибка: Файл не найден</b>\n\n{caption}",
                    reply_markup=admin_kb,
                    parse_mode='HTML'
                )
                return

            try:
                # Отправляем медиафайл используя FSInputFile с абсолютным путем
                file = FSInputFile(media_path)
                if media_type == "photo":
                    await message.bot.send_photo(
                        ADMIN_CHAT_ID,
                        file,
                        caption=caption,
                        reply_markup=admin_kb,
                        parse_mode='HTML'
                    )
                elif media_type == "video":
                    await message.bot.send_video(
                        ADMIN_CHAT_ID,
                        file,
                        caption=caption,
                        reply_markup=admin_kb,
                        parse_mode='HTML'
                    )
                else:  # document
                    await message.bot.send_document(
                        ADMIN_CHAT_ID,
                        file,
                        caption=caption,
                        reply_markup=admin_kb,
                        parse_mode='HTML'
                    )
            except Exception as e:
                logging.error(f"Ошибка при отправке медиафайла: {e}")
                await message.bot.send_message(
                    ADMIN_CHAT_ID,
                    f"⚠️ <b>Ошибка при отправке файла</b>\n\n{caption}",
                    reply_markup=admin_kb,
                    parse_mode='HTML'
                )
        else:
            # Отправляем текстовое сообщение
            await message.bot.send_message(
                ADMIN_CHAT_ID,
                f"🆘 <b>Новое обращение в поддержку!</b>\n\n"
                f"🔢 ID: <code>#{ticket_id}</code>\n"
                f"👤 Пользователь: {user.mention_html()}\n"
                f"🆔 ID: <code>{user.id}</code>\n\n"
                f"📝 Сообщение:\n<code>{ticket_text}</code>",
                reply_markup=admin_kb
            )
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления администратору: {e}")
        await message.bot.send_message(
            ADMIN_CHAT_ID,
            f"🆘 <b>Новое обращение в поддержку!</b>\n\n"
            f"🔢 ID: <code>#{ticket_id}</code>\n"
            f"👤 Пользователь: {user.mention_html()}\n"
            f"🆔 ID: <code>{user.id}</code>\n\n"
            f"⚠️ <b>Ошибка при загрузке медиафайла!</b>\n"
            f"📝 Сообщение:\n<code>{ticket_text}</code>",
            reply_markup=admin_kb
        )
    
    # Ответ пользователю
    media_info = "🖼️ Фото прикреплено" if media_type == "photo" else \
                 "🎥 Видео прикреплено" if media_type == "video" else \
                 "📄 Файл прикреплен" if media_type and media_type != "too_big" else ""
    
    await message.answer(
        f"✅ Ваше обращение <b>#{ticket_id}</b> принято! {media_info}\n"
        "Администратор свяжется с вами в ближайшее время.\n\n"
        "Вы можете посмотреть статус в разделе «✉️ Мои обращения»",
        reply_markup=get_main_menu()
    )
    await state.clear()

# Обработчик ответа администратора на тикет
@router.callback_query(F.data.startswith("reply_ticket_"))
async def reply_ticket_callback(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    ticket_id = callback.data.split("_")[2]
    ticket = get_ticket_info(ticket_id)
    
    if not ticket:
        await callback.answer("❌ Тикет не найден!", show_alert=True)
        return
    
    if ticket[8] != 'open':  # status
        await callback.answer("⚠️ Этот тикет уже закрыт!", show_alert=True)
        return
    
    # Сохраняем данные о тикете
    await state.update_data(
        ticket_id=ticket_id, 
        user_id=ticket[1],
        reply_text=""
    )
    
    # Формируем сообщение с информацией о тикете
    message_text = (
        f"✍️ Ответ на обращение #{ticket_id} от {ticket[3]}\n\n"
        f"<b>Сообщение пользователя:</b>\n<code>{ticket[5]}</code>"
    )
    
    # Добавляем информацию о медиафайле, если он есть
    if ticket[6] and ticket[6] != "too_big":  # media_type
        media_icon = "🖼️" if ticket[6] == "photo" else "🎥" if ticket[6] == "video" else "📄"
        media_info = f"\n\n{media_icon} <b>Пользователь прикрепил файл</b>"
        
        # Создаем кнопку для скачивания файла
        download_button = InlineKeyboardButton(
            text="⬇️ Скачать файл",
            callback_data=f"download_media_{ticket_id}"
        )
        
        # Создаем клавиатуру с кнопкой скачивания
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[download_button]])
        
        await callback.message.answer(
            message_text + media_info,
            reply_markup=keyboard
        )
    else:
        await callback.message.answer(
            message_text,
            reply_markup=ReplyKeyboardRemove()
        )
    
    # Просим администратора ввести ответ
    await callback.message.answer(
        "💬 Введите текст ответа для пользователя:",
        reply_markup=get_admin_reply_menu()
    )
    await state.update_data(bot=bot)  # Сохраняем бот в состоянии
    await state.set_state(SupportStates.ADMIN_REPLY)
    await callback.answer()

# Обработчик скачивания медиафайла
@router.callback_query(F.data.startswith("download_media_"))
async def download_media_callback(callback: types.CallbackQuery):
    try:
        ticket_id = callback.data.split("_")[2]
        ticket = get_ticket_info(ticket_id)
        
        if not ticket or not ticket[7]:  # media_path
            await callback.answer("❌ Файл не найден в базе данных!", show_alert=True)
            return
        
        media_path = ticket[7]
        media_type = ticket[6] if len(ticket) > 6 else "document"
        
        # Проверяем существование файла
        if not os.path.exists(media_path):
            logging.error(f"Файл не найден по пути: {media_path}")
            await callback.answer("❌ Файл не найден на сервере!", show_alert=True)
            return
            
        try:
            # Отправляем файл администратору используя FSInputFile
            file = FSInputFile(media_path)
            caption = f"📎 Файл из тикета #{ticket_id}"
            
            if media_type == "photo":
                await callback.bot.send_photo(
                    chat_id=callback.from_user.id,
                    photo=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            elif media_type == "video":
                await callback.bot.send_video(
                    chat_id=callback.from_user.id,
                    video=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            else:  # document
                await callback.bot.send_document(
                    chat_id=callback.from_user.id,
                    document=file,
                    caption=caption,
                    parse_mode='HTML'
                )
            
            await callback.answer("✅ Файл отправлен в ваш чат!")
            
        except Exception as e:
            logging.error(f"Ошибка при отправке файла {media_path}: {e}", exc_info=True)
            await callback.answer("❌ Ошибка при отправке файла. Проверьте логи.", show_alert=True)
            
    except Exception as e:
        logging.error(f"Неожиданная ошибка в download_media_callback: {e}", exc_info=True)
        await callback.answer("❌ Произошла ошибка при обработке запроса", show_alert=True)

async def send_final_reply(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ticket_id = data.get('ticket_id')
    ticket = get_ticket_info(ticket_id)
    
    if not ticket:
        await message.answer("❌ Ошибка: тикет не найден", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
        
    try:
        # Get values from ticket tuple by index
        # Assuming ticket tuple structure: (id, user_id, username, first_name, last_name, message_text, media_type, media_path, status, created_at)
        user_id = ticket[1]  # user_id is at index 1
        username = ticket[2]
        first_name = ticket[3]
        reply_text = data.get('reply_text', '')
        media_path = data.get('reply_media_path')
        media_type = data.get('reply_media_type')
        
        # Формируем сообщение с ответом
        response = f"📩 <b>Ответ на ваш тикет #{ticket_id}</b>\n\n{reply_text}"
        
        try:
            if media_path and os.path.exists(media_path):
                # Use FSInputFile which handles file operations internally
                try:
                    if media_type == 'photo':
                        await bot.send_photo(
                            chat_id=user_id,
                            photo=FSInputFile(media_path),
                            caption=response,
                            parse_mode='HTML'
                        )
                    elif media_type == 'video':
                        await bot.send_video(
                            chat_id=user_id,
                            video=FSInputFile(media_path),
                            caption=response,
                            parse_mode='HTML'
                        )
                    elif media_type == 'document':
                        await bot.send_document(
                            chat_id=user_id,
                            document=FSInputFile(media_path),
                            caption=response,
                            parse_mode='HTML'
                        )
                except Exception as file_error:
                    logging.error(f"Ошибка при отправке файла {media_path}: {file_error}", exc_info=True)
                    # Fallback to text message if file sending fails
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"{response}\n\n⚠️ Не удалось отправить вложение. Обратитесь в поддержку.",
                        parse_mode='HTML'
                    )
                    raise  # Re-raise to trigger the outer exception handler
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=response,
                    parse_mode='HTML'
                )
            
            # Обновляем статус тикета
            update_ticket_status(ticket_id, 'closed')
            
            # Отправляем подтверждение администратору
            await message.answer(
                f"✅ Ответ успешно отправлен пользователю @{username} ({first_name})",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Удаляем временный файл, если он существует
            if media_path and os.path.exists(media_path):
                try:
                    os.remove(media_path)
                except Exception as e:
                    logging.error(f"Ошибка при удалении временного файла: {e}")
                    
        except Exception as e:
            logging.error(f"Ошибка при отправке ответа: {e}")
            await message.answer(
                "❌ Не удалось отправить ответ. Пожалуйста, попробуйте снова.",
                reply_markup=ReplyKeyboardRemove()
            )
        
    except Exception as e:
        logging.error(f"Ошибка при обработке ответа: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке ответа",
            reply_markup=ReplyKeyboardRemove()
        )
    
    await state.clear()

# Обработчик текста ответа от администратора
@router.message(SupportStates.ADMIN_REPLY, F.text)
async def process_admin_reply(message: types.Message, state: FSMContext, bot: Bot = None):
    data = await state.get_data()
    
    # Если бот не передан как параметр, пробуем получить из состояния
    if bot is None:
        bot = data.get('bot')
        if bot is None:
            logging.error("Bot instance not found in state")
            await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.", reply_markup=ReplyKeyboardRemove())
            await state.clear()
            return
    
    if message.text == "❌ Отменить ответ":
        await message.answer("❌ Ответ отменен", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
    
    if message.text == "📎 Прикрепить файл":
        await message.answer(
            "📎 Прикрепите фото, видео или документ к ответу:",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(SupportStates.ADMIN_MEDIA)
        return
    
    if message.text == "📤 Отправить ответ":
        # Проверяем, есть ли текст ответа
        if not data.get('reply_text'):
            await message.answer("❌ Текст ответа не может быть пустым!")
            return
        
        # Отправляем ответ с передачей бота
        await send_final_reply(message, state, bot)
        return
    
    # Сохраняем текст ответа
    await state.update_data(reply_text=message.text)
    
    await message.answer(
        f"📝 Текст ответа сохранен:\n\n{message.text}\n\n"
        "Вы можете:\n"
        "1. 📎 Прикрепить файл к ответу\n"
        "2. 📤 Отправить ответ\n"
        "3. ❌ Отменить ответ",
        reply_markup=get_admin_reply_menu()
    )

# Обработчик медиа для ответа от администратора
@router.message(SupportStates.ADMIN_MEDIA)
async def process_admin_media(message: types.Message, state: FSMContext, bot: Bot = None):
    data = await state.get_data()
    
    # Если бот не передан как параметр, пробуем получить из состояния
    if bot is None:
        bot = data.get('bot')
        if bot is None:
            logging.error("Bot instance not found in state")
            await message.answer("❌ Произошла ошибка. Пожалуйста, попробуйте еще раз.", reply_markup=ReplyKeyboardRemove())
            await state.clear()
            return
            
    reply_media_type = None
    reply_media_path = None
    
    # Обработка медиафайлов
    if message.photo:
        media = message.photo[-1]  # Берем фото с самым высоким разрешением
        reply_media_type, reply_media_path = await save_media(media, message.from_user.id, bot)
    elif message.video:
        reply_media_type, reply_media_path = await save_media(message.video, message.from_user.id, bot)
    elif message.document:
        reply_media_type, reply_media_path = await save_media(message.document, message.from_user.id, bot)
    else:
        await message.answer("❌ Пожалуйста, прикрепите фото, видео или документ.")
        return
    
    # Обработка слишком больших файлов
    if reply_media_type == "too_big":
        await message.answer("❌ Файл слишком большой. Максимальный размер файла — 20 МБ для видео и документов.")
        return
    
    media_icon = "🖼️" if reply_media_type == "photo" else "🎥" if reply_media_type == "video" else "📄"
    
    # Сохраняем информацию о медиа
    await state.update_data(
        reply_media_type=reply_media_type,
        reply_media_path=reply_media_path
    )
    
    # Создаем клавиатуру для отправки ответа
    keyboard = [
        [KeyboardButton(text="📤 Отправить ответ")],
        [KeyboardButton(text="❌ Отменить ответ")]
    ]
    
    await message.answer(
        f"{media_icon} Файл прикреплен к ответу!\n\n"
        f"📝 Текст ответа:\n{data.get('reply_text', '')}\n\n"
        "Вы можете отправить ответ или отменить его:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True
        )
    )
    
    # Сохраняем бот в состоянии и устанавливаем состояние для обработки отправки ответа
    await state.update_data(bot=bot)
    await state.set_state(SupportStates.ADMIN_REPLY)

# ========== АДМИН КОМАНДЫ ========== #
@router.message(Command("addproxies"))
async def cmd_addproxies(message: types.Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return await message.answer("⛔ Доступ запрещён!", reply_markup=get_main_menu())
    
    try:
        if not message.reply_to_message or not message.reply_to_message.document:
            return await message.answer("ℹ️ Ответьте этой командой на файл с прокси (txt)")
        
        file = await message.bot.get_file(message.reply_to_message.document.file_id)
        file_name = message.reply_to_message.document.file_name
        
        # Проверяем расширение файла
        if not file_name.endswith('.txt'):
            return await message.answer("❌ Неподдерживаемый формат файла. Используйте .txt", reply_markup=get_main_menu())
        
        file_path = os.path.join(PROXY_FOLDER, file_name)
        await message.bot.download_file(file.file_path, file_path)
        
        # Добавляем в базу, если это новый файл
        display_name = os.path.splitext(file_name)[0].capitalize()
        add_proxy_file(file_name, display_name)
        
        proxies = load_proxies(file_name)
        await message.answer(
            f"✅ Файл '{file_name}' обновлён!\n"
            f"Загружено {len(proxies)} прокси\n"
            f"Тип: {display_name}",
            reply_markup=get_main_menu()
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}", reply_markup=get_main_menu())

@router.message(Command("tickets"))
async def list_tickets_handler(message: types.Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return await message.answer("⛔ Доступ запрещён!", reply_markup=get_main_menu())
    
    tickets = get_open_tickets()
    
    if not tickets:
        return await message.answer("ℹ️ Нет открытых обращений")
    
    tickets_text = "📬 <b>Открытые обращения:</b>\n\n"
    for ticket in tickets:
        date_str = format_date(ticket[9])
        
        # Информация о медиа
        media_info = ""
        if ticket[6] and ticket[6] != "too_big":  # media_type
            media_icon = "🖼️" if ticket[6] == "photo" else "🎥" if ticket[6] == "video" else "📄"
            media_info = f"\n{media_icon} Прикреплен файл"
        
        tickets_text += (
            f"<b>#{ticket[0]}</b>{media_info}\n"
            f"👤 {ticket[3]} (@{ticket[2]})\n"
            f"🆔 <code>{ticket[1]}</code>\n"
            f"📅 {date_str}\n\n"
        )
    
    await message.answer(tickets_text)

# ========== ОБРАБОТЧИКИ ИНЛАЙН-КНОПОК ========== #
@router.callback_query(F.data == "change_lang")
async def change_lang_callback(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru")
        ],
        [
            InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")
        ]
    ])
    await callback.message.edit_text("🌐 Выберите язык:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("set_lang_"))
async def set_lang_callback(callback: types.CallbackQuery):
    lang = callback.data.split("_")[-1]
    # Здесь должна быть функция обновления языка в БД
    text = "✅ Язык изменен на русский" if lang == "ru" else "✅ Language changed to English"
    await callback.message.edit_text(text)

@router.callback_query(F.data == "toggle_notify")
async def toggle_notify_callback(callback: types.CallbackQuery):
    # Здесь должна быть функция переключения уведомлений в БД
    await callback.message.edit_text("🔔 Уведомления переключены!")

# Обработчик текстовых сообщений в поддержке
@router.message(SupportStates.WAITING_MESSAGE, F.text)
async def support_text_handler(message: types.Message, state: FSMContext):
    await process_support_message(message, state)

# Обработчик фото в поддержке
@router.message(SupportStates.WAITING_MESSAGE, F.photo)
async def support_photo_handler(message: types.Message, state: FSMContext):
    await process_support_message(message, state)

# Обработчик видео в поддержке
@router.message(SupportStates.WAITING_MESSAGE, F.video)
async def support_video_handler(message: types.Message, state: FSMContext):
    await process_support_message(message, state)

# Обработчик документов в поддержке
@router.message(SupportStates.WAITING_MESSAGE, F.document)
async def support_document_handler(message: types.Message, state: FSMContext):
    await process_support_message(message, state)

# Обработчик неизвестных сообщений (должен быть последним)
@router.message()
async def unknown_message_handler(message: types.Message):
    await message.answer("🤔 Я не понимаю эту команду. Используйте меню для навигации.", reply_markup=get_main_menu())

# Обработчик неизвестных callback-запросов
@router.callback_query()
async def unknown_callback_handler(callback: types.CallbackQuery):
    await callback.answer("❌ Неизвестная команда", show_alert=True)

# Обработчик поддержки бота через ЮMoney
@router.message(F.text == "💖 Поддержать бота")
async def support_bot_handler(message: types.Message):
    # Создаем inline-кнопку с ссылкой на ЮMoney
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💳 Поддержать через ЮMoney",
                url="https://yoomoney.ru/transfer"
            )
        ]
    ])
    
    await message.answer(
        "💖 <b>Поддержите развитие бота!</b>\n\n"
        "Ваша поддержка поможет мне:\n"
        "• Улучшить функциональность бота\n"
        "• Обеспечить стабильную работу\n"
        "• Добавлять новые возможности\n\n"
        "<i>Для поддержки нажмите кнопку ниже:</i>\n\n"
        "<b>Реквизиты для поддержки:</b>\n"
        "ЮMoney: <code>4100 1182 5161 5761</code>",
        reply_markup=keyboard,
        parse_mode='HTML'
    )

# Функция для настройки всех обработчиков
def setup_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков"""
    
    # Регистрируем обработчики команд
    dp.message.register(cmd_start, Command("start"))
    
    # Обработчики для работы с прокси
    dp.message.register(get_proxy_handler, Command("getproxy"))
    dp.message.register(get_proxy_handler, F.text == "🍔 Получить прокси")
    dp.callback_query.register(get_proxy_callback, F.data.startswith("getproxy_"))
    
    # Обработчики для загрузки файлов
    dp.message.register(download_file_handler, Command("download"))
    dp.message.register(download_file_handler, F.text == "📥 Скачать файл")
    dp.callback_query.register(download_file_callback, F.data.startswith("download_"))
    
    # Обработчик статистики
    dp.message.register(show_statistics, F.text == "📊 Статистика")
    
    # Обработчики истории загрузок
    dp.message.register(cmd_downloads, Command("downloads"))
    dp.message.register(cmd_my_downloads, Command("mydownloads"))
    dp.message.register(my_files_handler, F.text == "📎 Мои файлы")
    dp.message.register(history_handler, F.text == "📜 История")
    
    # Обработчики поддержки
    dp.message.register(support_handler, F.text == "🆘 Поддержка")
    dp.message.register(support_handler, Command("support"))
    dp.message.register(my_tickets_handler, Command("mytickets"))
    dp.message.register(cancel_support_handler, Command("cancel"), F.text == "❌ Отмена")
    
    # Обработчики ответов администратора
    dp.callback_query.register(reply_ticket_callback, F.data.startswith("reply_ticket_"))
    dp.callback_query.register(download_media_callback, F.data.startswith("download_media_"))
    
    # Обработчики сообщений поддержки
    dp.message.register(process_support_message, SupportStates.WAITING_MESSAGE)
    dp.message.register(process_admin_reply, SupportStates.ADMIN_REPLY)
    
    # Обработчики медиа в поддержке
    dp.message.register(support_photo_handler, SupportStates.WAITING_MESSAGE, F.photo)
    dp.message.register(support_video_handler, SupportStates.WAITING_MESSAGE, F.video)
    dp.message.register(support_document_handler, SupportStates.WAITING_MESSAGE, F.document)
    
    # Обработчики медиа в ответах администратора
    dp.message.register(process_admin_media, SupportStates.ADMIN_MEDIA, F.photo | F.video | F.document)
    
    # Обработчики настроек
    dp.message.register(settings_handler, Command("settings"))
    dp.message.register(settings_handler, F.text == "⚙️ Настройки")
    dp.callback_query.register(change_lang_callback, F.data == "change_lang")
    dp.callback_query.register(set_lang_callback, F.data.startswith("set_lang_"))
    dp.callback_query.register(toggle_notify_callback, F.data == "toggle_notify")
    
    # Регистрируем обработчик для получения ссылок на файлы
    dp.callback_query.register(get_file_link_callback, F.data.startswith("link_"))
    
    # Регистрируем обработчик для поддержки бота
    dp.message.register(support_bot_handler, F.text == "💖 Поддержать бота")
    
    # Обработка неизвестных команд (должно быть в конце)
    dp.message.register(unknown_message_handler)
    dp.callback_query.register(unknown_callback_handler)