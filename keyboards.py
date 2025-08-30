from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🍔 Получить прокси"))
    builder.row(
        KeyboardButton(text="📜 История"),
        KeyboardButton(text="⚙️ Настройки")
    )
    builder.row(
        KeyboardButton(text="🆘 Поддержка"),
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="📥 Скачать файл")
    )
    builder.row(KeyboardButton(text="📎 Мои файлы"))
    return builder.as_markup(
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )

def get_support_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="✉️ Мои обращения"))
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)

def get_admin_reply_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📎 Прикрепить файл"))
    builder.row(KeyboardButton(text="📤 Отправить ответ"))
    builder.row(KeyboardButton(text="❌ Отменить ответ"))
    return builder.as_markup(resize_keyboard=True)