import json
import os
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

logger = logging.getLogger(__name__)
router = Router()

# Ma'lumotlarni yuklash
BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, "otm_directions.json")
SCORES_PATH = os.path.join(BASE_DIR, "scores_data.json")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    OTM_DATA = json.load(f)

SCORES_DATA = {}
if os.path.exists(SCORES_PATH):
    with open(SCORES_PATH, "r", encoding="utf-8") as f:
        SCORES_DATA = json.load(f)

class OTMState(StatesGroup):
    selecting_fan1 = State()
    selecting_fan2 = State()

@router.message(F.text == "🎓 OTM Yo'nalishlari")
async def start_otm_selection(message: Message, state: FSMContext):
    await state.set_state(OTMState.selecting_fan1)
    
    builder = InlineKeyboardBuilder()
    for fan in OTM_DATA["fan1_list"]:
        builder.button(text=fan, callback_data=f"otm_f1:{fan}")
    builder.adjust(2)
    
    await message.answer(
        "🎓 <b>OTM yo'nalishlarini aniqlash xizmati</b>\n\n"
        "Iltimos, <b>1-asosiy faningizni</b> tanlang:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

@router.callback_query(OTMState.selecting_fan1, F.data.startswith("otm_f1:"))
async def select_fan1(callback: CallbackQuery, state: FSMContext):
    fan1 = callback.data.split(":")[1]
    await state.update_data(fan1=fan1)
    await state.set_state(OTMState.selecting_fan2)
    
    fan2_list = list(OTM_DATA["data"].get(fan1, {}).keys())
    
    builder = InlineKeyboardBuilder()
    for fan in fan2_list:
        builder.button(text=fan, callback_data=f"otm_f2:{fan}")
    builder.button(text="🔙 Orqaga", callback_data="otm_back_f1")
    builder.adjust(2)
    
    await callback.message.edit_text(
        f"✅ 1-fan: <b>{fan1}</b>\n\n"
        f"Endi <b>2-asosiy faningizni</b> tanlang:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()

@router.callback_query(OTMState.selecting_fan2, F.data.startswith("otm_f2:"))
async def select_fan2(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    fan1 = data.get("fan1")
    fan2 = callback.data.split(":")[1]
    
    directions = OTM_DATA["data"].get(fan1, {}).get(fan2, [])
    
    if not directions:
        await callback.message.edit_text(
            f"❌ Kechirasiz, <b>{fan1}</b> va <b>{fan2}</b> fanlari kombinatsiyasi bo'yicha yo'nalishlar topilmadi.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Qayta tanlash", callback_data="otm_restart")]
            ])
        )
    else:
        text = f"📚 <b>Fanlar:</b> {fan1} + {fan2}\n"
        text += f"✅ <b>Jami yo'nalishlar:</b> {len(directions)}\n\n"
        text += "📋 <b>Yo'nalishlar ro'yxati:</b>\n"
        text += "<i>(Ballarni ko'rish uchun yo'nalishni tanlang)</i>\n\n"
        
        builder = InlineKeyboardBuilder()
        for d in directions:
            # Har bir yo'nalish uchun alohida tugma
            builder.button(text=f"{d['name']}", callback_data=f"otm_det:{d['code']}")
        
        builder.button(text="🔄 Qayta tanlash", callback_data="otm_restart")
        builder.button(text="🏠 Bosh menyu", callback_data="otm_home")
        builder.adjust(1)
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    
    await callback.answer()

@router.callback_query(F.data.startswith("otm_det:"))
async def show_direction_details(callback: CallbackQuery):
    code = callback.data.split(":")[1]
    scores = SCORES_DATA.get(code, [])
    
    # Yo'nalish nomini topish
    dir_name = "Noma'lum yo'nalish"
    for f1 in OTM_DATA["data"]:
        for f2 in OTM_DATA["data"][f1]:
            for d in OTM_DATA["data"][f1][f2]:
                if d["code"] == code:
                    dir_name = d["name"]
                    break
    
    text = f"🎯 <b>Yo'nalish:</b> {dir_name}\n"
    text += f"🔑 <b>Kodi:</b> <code>{code}</code>\n\n"
    
    if not scores:
        text += "⚠️ <i>Ushbu yo'nalish bo'yicha o'tish ballari haqida ma'lumot topilmadi.</i>"
    else:
        text += "📊 <b>2024-yilgi o'tish ballari:</b>\n\n"
        for s in scores[:15]: # Limit to avoid long messages
            text += f"🏛 <b>{s['otm']}</b> ({s['shakl']})\n"
            text += f"  Grant: <b>{s['grant']}</b> | Kontrakt: <b>{s['kontrakt']}</b>\n\n"
        
        if len(scores) > 15:
            text += f"<i>... va yana {len(scores)-15} ta OTM.</i>\n"
            
    text += "\n<i>Ma'lumotlar 2024-yilgi kirish natijalariga asoslangan.</i>"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Orqaga", callback_data="otm_restart")
    builder.button(text="🏠 Bosh menyu", callback_data="otm_home")
    builder.adjust(2)
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "otm_back_f1")
async def back_to_f1(callback: CallbackQuery, state: FSMContext):
    await start_otm_selection(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "otm_restart")
async def restart_otm(callback: CallbackQuery, state: FSMContext):
    await start_otm_selection(callback.message, state)
    await callback.answer()

@router.callback_query(F.data == "otm_home")
async def go_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("🏠 Asosiy menyuga qaytdingiz. Menyu tugmalaridan foydalanishingiz mumkin.")
    await callback.answer()
