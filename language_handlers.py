"""
Til tanlash handlerlari
Multi-language support uchun callback va message handlerlar
"""

from aiogram import Router, F, CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton

from i18n import i18n, get_user_text
from database import update_user_language, get_user_language, get_setting
from keyboards import user_menu_keyboard, admin_menu_keyboard, language_selection_keyboard, language_settings_keyboard
from admin import is_admin_id
from database import oqituvchi_ol

router = Router()

# Til tanlash uchun FSM holatlari
class LanguageState(StatesGroup):
    til_tanlash = State()

@router.callback_query(F.data.startswith("lang:"))
async def language_callback(callback: CallbackQuery, state: FSMContext):
    """Til tanlash callback handler"""
    user_id = callback.from_user.id
    action = callback.data.split(":")[1]
    
    if action == "select":
        await callback.message.edit_text(
            get_user_text(user_id, "language.select"),
            reply_markup=language_selection_keyboard()
        )
        await callback.answer()
    
    elif action in ["uz", "ru", "en"]:
        # Tilni o'rnatish
        if update_user_language(user_id, action):
            # Foydalanuvchi turiga qarab menuni yangilash
            await update_user_menu(callback.message, user_id, action)
            
            await callback.message.edit_text(
                get_user_text(user_id, "language.changed"),
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Til o'zgarganligi haqida xabar
            await callback.message.answer(
                get_user_text(user_id, "language.current", til=i18n.get_available_languages()[action]),
                reply_markup=get_user_keyboard(user_id, action)
            )
        else:
            await callback.answer("❌ Xatolik!", show_alert=True)
    
    await callback.answer()

async def update_user_menu(message: Message, user_id: int, language: str):
    """Foydalanuvchi menulisini tilga qarab yangilash"""
    # Admin tekshiruvi
    if is_admin_id(user_id):
        await message.answer(
            get_user_text(user_id, "admin.welcome"),
            reply_markup=admin_menu_keyboard()
        )
        return
    
    # O'qituvchi tekshiruvi
    teacher = oqituvchi_ol(user_id)
    if teacher:
        await message.answer(
            f"👋 Xush kelibsiz, {teacher['ismlar']}! ({teacher['sinf']} sinf rahbari)",
            reply_markup=get_teacher_keyboard(language)
        )
        return
    
    # Oddiy foydalanuvchi
    ranking_enabled = get_setting('ranking_enabled', 'True')
    stats_enabled = get_setting('stats_enabled', 'True')
    
    await message.answer(
        get_user_text(user_id, "start.welcome"),
        parse_mode="HTML",
        reply_markup=user_menu_keyboard(ranking_enabled, stats_enabled)
    )

def get_user_keyboard(user_id: int, language: str):
    """Foydalanuvchi turiga qarab klaviatura qaytarish"""
    if is_admin_id(user_id):
        return admin_menu_keyboard()
    
    teacher = oqituvchi_ol(user_id)
    if teacher:
        return get_teacher_keyboard(language)
    
    # Oddiy foydalanuvchi klaviaturasi
    ranking_enabled = get_setting('ranking_enabled', 'True')
    stats_enabled = get_setting('stats_enabled', 'True')
    return user_menu_keyboard(ranking_enabled, stats_enabled)

def get_teacher_keyboard(language: str):
    """O'qituvchi klaviaturasi"""
    if language == 'ru':
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊 Мои результаты"), KeyboardButton(text="👤 Личный кабинет")],
                [KeyboardButton(text="📈 Статистика"), KeyboardButton(text="🧠 AI анализ")],
                [KeyboardButton(text="✍️ Связаться с администратором"), KeyboardButton(text="🚪 Выход")]
            ],
            resize_keyboard=True
        )
    elif language == 'en':
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊 My results"), KeyboardButton(text="👤 Personal cabinet")],
                [KeyboardButton(text="📈 Statistics"), KeyboardButton(text="🧠 AI Analysis")],
                [KeyboardButton(text="✍️ Contact admin"), KeyboardButton(text="🚪 Exit")]
            ],
            resize_keyboard=True
        )
    else:  # Uzbek (default)
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊 Mening natijalarim"), KeyboardButton(text="👤 Shaxsiy kabinet")],
                [KeyboardButton(text="📈 Statistika"), KeyboardButton(text="🧠 AI Tahlili")],
                [KeyboardButton(text="✍️ Admin bilan bog'lanish"), KeyboardButton(text="🚪 Chiqish")]
            ],
            resize_keyboard=True
        )

@router.message(F.text.startswith("🌐"))
async def language_command(message: Message, state: FSMContext):
    """Til o'zgartirish komandasi"""
    user_id = message.from_user.id
    
    await message.answer(
        get_user_text(user_id, "language.select"),
        reply_markup=language_selection_keyboard()
    )

# Til sozlamalari uchun callback
@router.callback_query(F.data.startswith("menu:"))
async def menu_callback(callback: CallbackQuery, state: FSMContext):
    """Menuga qaytish callback"""
    user_id = callback.from_user.id
    
    if callback.data.split(":")[1] == "main":
        await callback.message.edit_text(
            get_user_text(user_id, "language.current", til=i18n.get_available_languages()[get_user_language(user_id)]),
            reply_markup=get_user_keyboard(user_id, get_user_language(user_id))
        )
    
    await callback.answer()
