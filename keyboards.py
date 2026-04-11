from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from database import yonalish_ol, sinf_ol


def admin_menu_keyboard():
    """Admin bosh menyusi — reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ O'quvchi qo'shish")],
            [KeyboardButton(text="📥 Exceldan import")],
            [KeyboardButton(text="✏️ Natijani tahrirlash")],
            [KeyboardButton(text="⚙️ Yo'nalishlarni boshqarish")],
            [KeyboardButton(text="🏫 Sinflarni boshqarish")],
            [KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="📊 Chuqur tahlil")],
            [KeyboardButton(text="📋 O'quvchilar ro'yxati")],
            [KeyboardButton(text="📥 Excelga yuklash")],
            [KeyboardButton(text="🧹 Bazani tozalash")],
            [KeyboardButton(text="📢 Xabar yuborish")],
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


def sinf_keyboard():
    """Sinflarni inline tugmalar sifatida chiqaradi (dinamik)."""
    buttons = []
    sinflar = sinf_ol()
    for s in sinflar:
        buttons.append([InlineKeyboardButton(text=s, callback_data=f"sinf:{s}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def yonalish_boshqarish_keyboard():
    """Yo'nalishlarni boshqarish menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Mavjud yo'nalishlar", callback_data="yonalish_boshqar:ro'yxat")],
        [InlineKeyboardButton(text="➕ Yangi yo'nalish qo'shish", callback_data="yonalish_boshqar:qosh")],
        [InlineKeyboardButton(text="❌ Yo'nalishni o'chirish", callback_data="yonalish_boshqar:ochir")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="yonalish_boshqar:orqaga")],
    ])


def sinf_boshqarish_keyboard():
    """Sinflarni boshqarish menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Mavjud sinflar", callback_data="sinf_boshqar:ro'yxat")],
        [InlineKeyboardButton(text="➕ Yangi sinf qo'shish", callback_data="sinf_boshqar:qosh")],
        [InlineKeyboardButton(text="❌ Sinfni o'chirish", callback_data="sinf_boshqar:ochir")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="sinf_boshqar:orqaga")],
    ])


def yonalish_ochirish_keyboard():
    """Yo'nalishlarni o'chirish uchun ro'yxat."""
    buttons = []
    yonalishlar = yonalish_ol()
    for y in yonalishlar:
        buttons.append([InlineKeyboardButton(text=f"❌ {y}", callback_data=f"yonalish_ochir:{y}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="yonalish_boshqar:orqaga")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_ochirish_keyboard():
    """Sinflarni o'chirish uchun ro'yxat."""
    buttons = []
    sinflar = sinf_ol()
    for s in sinflar:
        buttons.append([InlineKeyboardButton(text=f"❌ {s}", callback_data=f"sinf_ochir:{s}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="sinf_boshqar:orqaga")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tasdiqlash_keyboard():
    """✅ Saqlash / ❌ Bekor qilish tugmalari."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Saqlash", callback_data="tasdiq:ha"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tasdiq:yoq"),
        ]
    ])


def user_menu_keyboard():
    """Foydalanuvchi asosiy menyusi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Mening natijalarim")],
            [KeyboardButton(text="✍️ Admin bilan bog'lanish")],
        ],
        resize_keyboard=True
    )


def murojaat_bekor_qilish_keyboard():
    """Murojaatni bekor qilish tugmasi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True
    )


def murojaat_javob_keyboard(user_id):
    """Admin uchun murojaatga javob berish tugmasi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Javob berish", callback_data=f"murojaat_javob:{user_id}")]
    ])
