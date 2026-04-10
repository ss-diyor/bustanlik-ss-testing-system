from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from config import YONALISHLAR


def admin_menu_keyboard():
    """Admin bosh menyusi — reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ O'quvchi qo'shish")],
            [KeyboardButton(text="✏️ Natijani tahrirlash")],
            [KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="🔍 Kod bo'yicha qidirish")],
            [KeyboardButton(text="🚪 Chiqish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def yonalish_keyboard():
    """Yo'nalishlarni inline tugmalar sifatida chiqaradi."""
    buttons = []
    for y in YONALISHLAR:
        buttons.append([InlineKeyboardButton(text=y, callback_data=f"yonalish:{y}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tasdiqlash_keyboard():
    """✅ Saqlash / ❌ Bekor qilish tugmalari."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Saqlash", callback_data="tasdiq:ha"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tasdiq:yoq"),
        ]
    ])
