from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_PASSWORD, MAX_SAVOL
from database import (
    talaba_qosh, talaba_yangilash, talaba_topish, statistika, ball_hisobla,
    yonalish_ol, yonalish_qosh, yonalish_ochir, talaba_hammasi,
    kalit_qosh, kalit_ol
)
from keyboards import (
    admin_menu_keyboard, yonalish_keyboard, tasdiqlash_keyboard,
    yonalish_boshqarish_keyboard, yonalish_ochirish_keyboard,
    kalitlar_boshqarish_keyboard
)

router = Router()

# ─────────────────────────────────────────
# FSM holatlari
# ─────────────────────────────────────────

class AdminLogin(StatesGroup):
    parol_kutish = State()

class TalabaQosh(StatesGroup):
    kod_kutish = State()
    yonalish_kutish = State()
    majburiy_kutish = State()
    asosiy1_kutish = State()
    asosiy2_kutish = State()
    tasdiq_kutish = State()

class TalabaTahrir(StatesGroup):
    kod_kutish = State()
    yonalish_kutish = State()
    majburiy_kutish = State()
    asosiy1_kutish = State()
    asosiy2_kutish = State()
    tasdiq_kutish = State()

class KodQidirish(StatesGroup):
    kod_kutish = State()

class YonalishBoshqar(StatesGroup):
    nomi_kutish = State()

class KalitBoshqar(StatesGroup):
    yonalish_kutish = State()
    majburiy_kutish = State()
    asosiy1_kutish = State()
    asosiy2_kutish = State()
    tasdiq_kutish = State()

# ─────────────────────────────────────────
# Yordamchi funksiyalar
# ─────────────────────────────────────────

async def admin_tekshir(state: FSMContext) -> bool:
    data = await state.get_data()
    return data.get("admin") is True

def _son_tekshir(text: str):
    try:
        son = int(text)
        if 0 <= son <= MAX_SAVOL:
            return son
    except ValueError:
        pass
    return None

# ─────────────────────────────────────────
# /admin va Kirish
# ─────────────────────────────────────────

@router.message(F.text == "/admin")
async def admin_start(message: Message, state: FSMContext):
    if await admin_tekshir(state):
        await message.answer("✅ Siz allaqachon admin rejimidasiz.",
                             reply_markup=admin_menu_keyboard())
        return

    await state.set_state(AdminLogin.parol_kutish)
    await message.answer("🔐 Admin paroli kiriting:")


@router.message(AdminLogin.parol_kutish)
async def parol_tekshir(message: Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASSWORD:
        await state.update_data(admin=True)
        await state.set_state(None)
        await message.answer("✅ Xush kelibsiz, admin!",
                             reply_markup=admin_menu_keyboard())
    else:
        await message.answer("❌ Noto'g'ri parol. Qayta urinib ko'ring yoki /start bosing.")
        await state.clear()


@router.message(F.text == "🚪 Chiqish")
async def chiqish(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Admin rejimidan chiqdingiz.", reply_markup=None)

# ─────────────────────────────────────────
# Yo'nalishlarni boshqarish
# ─────────────────────────────────────────

@router.message(F.text == "⚙️ Yo'nalishlarni boshqarish")
async def yonalish_boshqar_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await message.answer("Yo'nalishlarni boshqarish menyusi:", 
                         reply_markup=yonalish_boshqarish_keyboard())


@router.callback_query(F.data.startswith("yonalish_boshqar:"))
async def yonalish_boshqar_actions(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    
    if action == "ro'yxat":
        yonalishlar = yonalish_ol()
        text = "📋 <b>Mavjud yo'nalishlar:</b>\n\n" + "\n".join([f"{i+1}. {y}" for i, y in enumerate(yonalishlar)]) if yonalishlar else "⚠️ Yo'nalishlar yo'q."
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=yonalish_boshqarish_keyboard())

    elif action == "qosh":
        await state.set_state(YonalishBoshqar.nomi_kutish)
        await callback.message.edit_text("📝 Yangi yo'nalish nomini kiriting:")
    
    elif action == "ochir":
        await callback.message.edit_text("❌ O'chirmoqchi bo'lgan yo'nalishni tanlang:",
                                         reply_markup=yonalish_ochirish_keyboard())
    
    elif action == "orqaga":
        await state.set_state(None)
        await callback.message.edit_text("Yo'nalishlarni boshqarish menyusi:", 
                                         reply_markup=yonalish_boshqarish_keyboard())

# ─────────────────────────────────────────
# Kalitlarni boshqarish
# ─────────────────────────────────────────

@router.message(F.text == "🔑 Kalitlarni boshqarish")
async def kalit_boshqar_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await message.answer("🔑 Kalitlarni boshqarish menyusi:", 
                         reply_markup=kalitlar_boshqarish_keyboard())


@router.callback_query(F.data.startswith("kalit_boshqar:"))
async def kalit_boshqar_actions(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    
    if action == "ro'yxat":
        yonalishlar = yonalish_ol()
        text = "📋 <b>Mavjud kalitlar:</b>\n\n"
        for y in yonalishlar:
            k = kalit_ol(y)
            status = "✅ Kiritilgan" if k else "❌ Kiritilmagan"
            text += f"• {y}: {status}\n"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kalitlar_boshqarish_keyboard())

    elif action == "qosh":
        await state.set_state(KalitBoshqar.yonalish_kutish)
        await callback.message.edit_text("🎯 Kalit kiritmoqchi bo'lgan yo'nalishni tanlang:", 
                                         reply_markup=yonalish_keyboard())
    
    elif action == "orqaga":
        await state.set_state(None)
        await callback.message.edit_text("Admin menyusi:", reply_markup=admin_menu_keyboard())


@router.callback_query(KalitBoshqar.yonalish_kutish, F.data.startswith("yonalish:"))
async def kalit_yonalish_tanla(callback: CallbackQuery, state: FSMContext):
    yonalish = callback.data.split(":", 1)[1]
    await state.update_data(yonalish=yonalish)
    await state.set_state(KalitBoshqar.majburiy_kutish)
    await callback.message.edit_text(f"✅ Yo'nalish: <b>{yonalish}</b>\n\n📝 <b>Majburiy fanlar</b> uchun to'g'ri javoblar kalitini kiriting ({MAX_SAVOL} ta):\n<i>Masalan: abcdabcd...</i>", parse_mode="HTML")


@router.message(KalitBoshqar.majburiy_kutish)
async def kalit_majburiy(message: Message, state: FSMContext):
    keys = message.text.strip().lower()
    if len(keys) != MAX_SAVOL:
        await message.answer(f"❌ Xato! Kalitlar soni roppa-rosa {MAX_SAVOL} ta bo'lishi kerak. Siz {len(keys)} ta kiritdingiz. Qayta kiriting:")
        return
    await state.update_data(majburiy=keys)
    await state.set_state(KalitBoshqar.asosiy1_kutish)
    await message.answer(f"✅ Majburiy kalitlar saqlandi.\n\n📝 <b>1-asosiy fan</b> uchun to'g'ri javoblar kalitini kiriting ({MAX_SAVOL} ta):", parse_mode="HTML")


@router.message(KalitBoshqar.asosiy1_kutish)
async def kalit_asosiy1(message: Message, state: FSMContext):
    keys = message.text.strip().lower()
    if len(keys) != MAX_SAVOL:
        await message.answer(f"❌ Xato! Kalitlar soni {MAX_SAVOL} ta bo'lishi kerak. Qayta kiriting:")
        return
    await state.update_data(asosiy1=keys)
    await state.set_state(KalitBoshqar.asosiy2_kutish)
    await message.answer(f"✅ 1-asosiy fan kalitlari saqlandi.\n\n📝 <b>2-asosiy fan</b> uchun to'g'ri javoblar kalitini kiriting ({MAX_SAVOL} ta):", parse_mode="HTML")


@router.message(KalitBoshqar.asosiy2_kutish)
async def kalit_asosiy2(message: Message, state: FSMContext):
    keys = message.text.strip().lower()
    if len(keys) != MAX_SAVOL:
        await message.answer(f"❌ Xato! Kalitlar soni {MAX_SAVOL} ta bo'lishi kerak. Qayta kiriting:")
        return
    data = await state.get_data()
    await state.update_data(asosiy2=keys)
    await state.set_state(KalitBoshqar.tasdiq_kutish)
    await message.answer(f"📋 <b>Kalitlarni tasdiqlang:</b>\n\nYo'nalish: {data['yonalish']}\nMajburiy: {data['majburiy']}\n1-Asosiy: {data['asosiy1']}\n2-Asosiy: {keys}", reply_markup=tasdiqlash_keyboard(), parse_mode="HTML")


@router.callback_query(KalitBoshqar.tasdiq_kutish, F.data.startswith("tasdiq:"))
async def kalit_tasdiq(callback: CallbackQuery, state: FSMContext):
    if callback.data.split(":")[1] == "ha":
        data = await state.get_data()
        kalit_qosh(data['yonalish'], data['majburiy'], data['asosiy1'], data['asosiy2'])
        await callback.message.edit_text(f"✅ <b>{data['yonalish']}</b> uchun kalitlar muvaffaqiyatli saqlandi!", parse_mode="HTML")
    else:
        await callback.message.edit_text("❌ Bekor qilindi.")
    await state.set_state(None)
    await callback.message.answer("Keyingi amal:", reply_markup=admin_menu_keyboard())

# ─────────────────────────────────────────
# O'quvchi QO'SHISH va TAHRIRLASH (oldingi kodlar)
# ─────────────────────────────────────────

@router.message(F.text == "➕ O'quvchi qo'shish")
async def talaba_qosh_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await state.set_state(TalabaQosh.kod_kutish)
    await message.answer("📝 O'quvchining shaxsiy <b>kodini</b> kiriting:", parse_mode="HTML")

@router.message(TalabaQosh.kod_kutish)
async def talaba_kod(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    if talaba_topish(kod):
        await message.answer(f"⚠️ <b>{kod}</b> kodi allaqachon bazada mavjud!")
        return
    await state.update_data(kod=kod)
    await state.set_state(TalabaQosh.yonalish_kutish)
    await message.answer(f"✅ Kod: <b>{kod}</b>\n\nYo'nalishni tanlang:", reply_markup=yonalish_keyboard(), parse_mode="HTML")

@router.callback_query(TalabaQosh.yonalish_kutish, F.data.startswith("yonalish:"))
async def talaba_yonalish(callback: CallbackQuery, state: FSMContext):
    yonalish = callback.data.split(":", 1)[1]
    await state.update_data(yonalish=yonalish)
    await state.set_state(TalabaQosh.majburiy_kutish)
    await callback.message.edit_text(f"✅ Yo'nalish: <b>{yonalish}</b>\n\nMajburiy fanlar (0-{MAX_SAVOL}) to'g'ri javoblar:", parse_mode="HTML")

@router.message(TalabaQosh.majburiy_kutish)
async def talaba_majburiy(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None: return
    await state.update_data(majburiy=son)
    await state.set_state(TalabaQosh.asosiy1_kutish)
    await message.answer(f"✅ Majburiy: <b>{son}</b> ta\n\n1-asosiy fan (0-{MAX_SAVOL}) to'g'ri javoblar:", parse_mode="HTML")

@router.message(TalabaQosh.asosiy1_kutish)
async def talaba_asosiy1(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None: return
    await state.update_data(asosiy_1=son)
    await state.set_state(TalabaQosh.asosiy2_kutish)
    await message.answer(f"✅ 1-asosiy: <b>{son}</b> ta\n\n2-asosiy fan (0-{MAX_SAVOL}) to'g'ri javoblar:", parse_mode="HTML")

@router.message(TalabaQosh.asosiy2_kutish)
async def talaba_asosiy2(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None: return
    data = await state.get_data()
    ball = ball_hisobla(data["majburiy"], data["asosiy_1"], son)
    await state.update_data(asosiy_2=son, ball=ball)
    await state.set_state(TalabaQosh.tasdiq_kutish)
    await message.answer(f"📋 Tasdiqlang:\nKod: {data['kod']}\nYo'nalish: {data['yonalish']}\nBall: {ball}", reply_markup=tasdiqlash_keyboard())

@router.callback_query(TalabaQosh.tasdiq_kutish, F.data.startswith("tasdiq:"))
async def talaba_tasdiq(callback: CallbackQuery, state: FSMContext):
    if callback.data.split(":")[1] == "ha":
        data = await state.get_data()
        talaba_qosh(data["kod"], data["yonalish"], data["majburiy"], data["asosiy_1"], data["asosiy_2"])
        await callback.message.edit_text(f"✅ {data['kod']} saqlandi!")
    else:
        await callback.message.edit_text("❌ Bekor qilindi.")
    await state.set_state(None)
    await callback.message.answer("Keyingi amal:", reply_markup=admin_menu_keyboard())

@router.message(F.text == "✏️ Natijani tahrirlash")
async def tahrir_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await state.set_state(TalabaTahrir.kod_kutish)
    await message.answer("✏️ Tahrirlamoqchi bo'lgan o'quvchining <b>kodini</b> kiriting:", parse_mode="HTML")

@router.message(TalabaTahrir.kod_kutish)
async def tahrir_kod(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer(f"❌ <b>{kod}</b> kodi topilmadi. Qayta kiriting:", parse_mode="HTML")
        return
    await state.update_data(kod=kod)
    await state.set_state(TalabaTahrir.yonalish_kutish)
    await message.answer(f"🔍 Topildi: <b>{kod}</b>\nJoriy ball: {talaba['umumiy_ball']}\n\nYangi yo'nalishni tanlang:", reply_markup=yonalish_keyboard(), parse_mode="HTML")

@router.callback_query(TalabaTahrir.yonalish_kutish, F.data.startswith("yonalish:"))
async def tahrir_yonalish(callback: CallbackQuery, state: FSMContext):
    yonalish = callback.data.split(":", 1)[1]
    await state.update_data(yonalish=yonalish)
    await state.set_state(TalabaTahrir.majburiy_kutish)
    await callback.message.edit_text(f"📝 Yangi yo'nalish: <b>{yonalish}</b>\n\nMajburiy fanlar (0-{MAX_SAVOL}) to'g'ri javoblar:", parse_mode="HTML")

@router.message(TalabaTahrir.majburiy_kutish)
async def tahrir_majburiy(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None: return
    await state.update_data(majburiy=son)
    await state.set_state(TalabaTahrir.asosiy1_kutish)
    await message.answer(f"✅ Majburiy: <b>{son}</b> ta\n\n1-asosiy fan (0-{MAX_SAVOL}) to'g'ri javoblar:", parse_mode="HTML")

@router.message(TalabaTahrir.asosiy1_kutish)
async def tahrir_asosiy1(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None: return
    await state.update_data(asosiy_1=son)
    await state.set_state(TalabaTahrir.asosiy2_kutish)
    await message.answer(f"✅ 1-asosiy: <b>{son}</b> ta\n\n2-asosiy fan (0-{MAX_SAVOL}) to'g'ri javoblar:", parse_mode="HTML")

@router.message(TalabaTahrir.asosiy2_kutish)
async def tahrir_asosiy2(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None: return
    data = await state.get_data()
    ball = ball_hisobla(data["majburiy"], data["asosiy_1"], son)
    await state.update_data(asosiy_2=son, ball=ball)
    await state.set_state(TalabaTahrir.tasdiq_kutish)
    await message.answer(f"📋 Yangi ma'lumotlarni tasdiqlang:\nKod: {data['kod']}\nYo'nalish: {data['yonalish']}\nBall: {ball}", reply_markup=tasdiqlash_keyboard())

@router.callback_query(TalabaTahrir.tasdiq_kutish, F.data.startswith("tasdiq:"))
async def tahrir_tasdiq(callback: CallbackQuery, state: FSMContext):
    if callback.data.split(":")[1] == "ha":
        data = await state.get_data()
        talaba_yangilash(data["kod"], data["yonalish"], data["majburiy"], data["asosiy_1"], data["asosiy_2"])
        await callback.message.edit_text(f"✅ {data['kod']} natijalari yangilandi!")
    else:
        await callback.message.edit_text("❌ Tahrirlash bekor qilindi.")
    await state.set_state(None)
    await callback.message.answer("Keyingi amal:", reply_markup=admin_menu_keyboard())

@router.message(F.text == "📊 Statistika")
async def admin_stat(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    talabalar = talaba_hammasi()
    if not talabalar:
        await message.answer("⚠️ Ma'lumot yo'q.")
        return
    text = "📊 <b>Natijalar:</b>\n\n"
    for i, t in enumerate(talabalar, 1):
        line = f"{i}. <b>{t['kod']}</b> | {t['umumiy_ball']} | {t['yonalish']}\n"
        if len(text + line) > 4000:
            await message.answer(text, parse_mode="HTML")
            text = ""
        text += line
    if text: await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🔍 Kod bo'yicha qidirish")
async def qidirish_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await state.set_state(KodQidirish.kod_kutish)
    await message.answer("🔍 Kodni kiriting:")

@router.message(KodQidirish.kod_kutish)
async def qidirish_natija(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    t = talaba_topish(kod)
    if t:
        text = f"👤 <b>Ma'lumotlar:</b>\n\nKod: {t['kod']}\nYo'nalish: {t['yonalish']}\nBall: {t['umumiy_ball']}"
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("❌ Topilmadi.")
    await state.set_state(None)
