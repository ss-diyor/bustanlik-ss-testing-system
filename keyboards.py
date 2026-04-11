from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from database import yonalish_ol


def admin_menu_keyboard():
    """Admin bosh menyusi — reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ O'quvchi qo'shish")],
            [KeyboardButton(text="✏️ Natijani tahrirlash")],
            [KeyboardButton(text="⚙️ Yo'nalishlarni boshqarish")],
            [KeyboardButton(text="🔑 Kalitlarni boshqarish")],
            [KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="🔍 Kod bo'yicha qidirish")],
            [KeyboardButton(text="🚪 Chiqish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def yonalish_keyboard():
    """Yo'nalishlarni inline tugmalar sifatida chiqaradi (dinamik)."""
    buttons = []
    yonalishlar = yonalish_ol()
    for y in yonalishlar:
        buttons.append([InlineKeyboardButton(text=y, callback_data=f"yonalish:{y}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def yonalish_boshqarish_keyboard():
    """Yo'nalishlarni boshqarish menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Mavjud yo'nalishlar", callback_data="yonalish_boshqar:ro'yxat")],
        [InlineKeyboardButton(text="➕ Yangi yo'nalish qo'shish", callback_data="yonalish_boshqar:qosh")],
        [InlineKeyboardButton(text="❌ Yo'nalishni o'chirish", callback_data="yonalish_boshqar:ochir")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="yonalish_boshqar:orqaga")],
    ])


def yonalish_ochirish_keyboard():
    """Yo'nalishlarni o'chirish uchun ro'yxat."""
    buttons = []
    yonalishlar = yonalish_ol()
    for y in yonalishlar:
        buttons.append([InlineKeyboardButton(text=f"❌ {y}", callback_data=f"yonalish_ochir:{y}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="yonalish_boshqar:orqaga")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def kalitlar_boshqarish_keyboard():
    """Kalitlarni boshqarish menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Mavjud kalitlar", callback_data="kalit_boshqar:ro'yxat")],
        [InlineKeyboardButton(text="➕ Kalit qo'shish / tahrirlash", callback_data="kalit_boshqar:qosh")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="kalit_boshqar:orqaga")],
    ])


def tasdiqlash_keyboard():
    """✅ Saqlash / ❌ Bekor qilish tugmalari."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Saqlash", callback_data="tasdiq:ha"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tasdiq:yoq"),
        ]
    ])
