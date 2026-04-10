from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_PASSWORD, MAX_SAVOL
from database import talaba_qosh, talaba_yangilash, talaba_topish, statistika, ball_hisobla
from keyboards import admin_menu_keyboard, yonalish_keyboard, tasdiqlash_keyboard

router = Router()

# ─────────────────────────────────────────
# FSM holatlari (State Machine)
# ─────────────────────────────────────────
# Har bir State — bu suhbatning bir "bosqichi".
# Bot foydalanuvchi qaysi bosqichda ekanini "eslab" turadi.

class AdminLogin(StatesGroup):
    parol_kutish = State()        # parol kiritilishini kutmoqda

class TalabaQosh(StatesGroup):
    kod_kutish = State()          # o'quvchi kodi
    yonalish_kutish = State()     # yo'nalish tanlash
    majburiy_kutish = State()     # majburiy fanlar natijasi
    asosiy1_kutish = State()      # 1-asosiy fan natijasi
    asosiy2_kutish = State()      # 2-asosiy fan natijasi
    tasdiq_kutish = State()       # saqlash tasdiqi

class TalabaTahrir(StatesGroup):
    kod_kutish = State()          # tahrirlanadigan o'quvchi kodi
    yonalish_kutish = State()
    majburiy_kutish = State()
    asosiy1_kutish = State()
    asosiy2_kutish = State()
    tasdiq_kutish = State()

class KodQidirish(StatesGroup):
    kod_kutish = State()

# ─────────────────────────────────────────
# Yordamchi funksiya: foydalanuvchi admin ekanini tekshiradi
# ─────────────────────────────────────────

async def admin_tekshir(state: FSMContext) -> bool:
    """State'da 'admin' kaliti bor bo'lsa True qaytaradi."""
    data = await state.get_data()
    return data.get("admin") is True


# ─────────────────────────────────────────
# /admin buyrug'i — kirish jarayonini boshlaydi
# ─────────────────────────────────────────

@router.message(F.text == "/admin")
async def admin_start(message: Message, state: FSMContext):
    # Agar allaqachon admin bo'lsa, menyuni ko'rsatadi
    if await admin_tekshir(state):
        await message.answer("✅ Siz allaqachon admin rejimidasiz.",
                             reply_markup=admin_menu_keyboard())
        return

    await state.set_state(AdminLogin.parol_kutish)
    await message.answer("🔐 Admin paroli kiriting:")


@router.message(AdminLogin.parol_kutish)
async def parol_tekshir(message: Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASSWORD:
        # Parol to'g'ri — admin holatini saqlaydi
        await state.update_data(admin=True)
        await state.set_state(None)  # FSM holatini tozalaydi
        await message.answer("✅ Xush kelibsiz, admin!\n\nNima qilmoqchisiz?",
                             reply_markup=admin_menu_keyboard())
    else:
        await message.answer("❌ Noto'g'ri parol. Qayta urinib ko'ring yoki /start bosing.")
        await state.clear()


# ─────────────────────────────────────────
# Chiqish
# ─────────────────────────────────────────

@router.message(F.text == "🚪 Chiqish")
async def chiqish(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Admin rejimidan chiqdingiz.\n\nKodingizni kiriting yoki /admin orqali qaytishingiz mumkin.",
                         reply_markup=None)


# ─────────────────────────────────────────
# O'quvchi QO'SHISH jarayoni (5 bosqich)
# ─────────────────────────────────────────

@router.message(F.text == "➕ O'quvchi qo'shish")
async def talaba_qosh_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state):
        await message.answer("⛔ Ruxsat yo'q. /admin orqali kiring.")
        return

    await state.set_state(TalabaQosh.kod_kutish)
    await message.answer(
        "📝 <b>O'quvchi qo'shish (1/5)</b>\n\n"
        "O'quvchining shaxsiy <b>kodini</b> kiriting:\n"
        "<i>Masalan: A-001, 52B, KD-007</i>",
        parse_mode="HTML"
    )


@router.message(TalabaQosh.kod_kutish)
async def talaba_kod(message: Message, state: FSMContext):
    kod = message.text.strip().upper()

    # Avval bu kod bazada borligini tekshiramiz
    mavjud = talaba_topish(kod)
    if mavjud:
        await message.answer(
            f"⚠️ <b>{kod}</b> kodi allaqachon bazada mavjud!\n\n"
            f"Tahrirlash uchun: ✏️ Natijani tahrirlash\n"
            f"Yoki boshqa kod kiriting:",
            parse_mode="HTML"
        )
        return  # holatni o'zgartirmaydi, qaytadan kod kutadi

    await state.update_data(kod=kod)
    await state.set_state(TalabaQosh.yonalish_kutish)
    await message.answer(
        f"✅ Kod: <b>{kod}</b>\n\n"
        "📚 <b>O'quvchi qo'shish (2/5)</b>\n\n"
        "Yo'nalishni tanlang:",
        reply_markup=yonalish_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(TalabaQosh.yonalish_kutish, F.data.startswith("yonalish:"))
async def talaba_yonalish(callback: CallbackQuery, state: FSMContext):
    yonalish = callback.data.split(":", 1)[1]
    await state.update_data(yonalish=yonalish)
    await state.set_state(TalabaQosh.majburiy_kutish)
    await callback.message.edit_text(
        f"✅ Yo'nalish: <b>{yonalish}</b>\n\n"
        f"📝 <b>O'quvchi qo'shish (3/5)</b>\n\n"
        f"<b>Majburiy fanlar</b> (Ona tili + Matematika + Tarix) bo'yicha\n"
        f"nechta to'g'ri javob? <i>(0 – {MAX_SAVOL})</i>",
        parse_mode="HTML"
    )


@router.message(TalabaQosh.majburiy_kutish)
async def talaba_majburiy(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ Iltimos, 0 dan {MAX_SAVOL} gacha son kiriting.")
        return

    await state.update_data(majburiy=son)
    await state.set_state(TalabaQosh.asosiy1_kutish)
    data = await state.get_data()
    await message.answer(
        f"✅ Majburiy: <b>{son}</b> ta to'g'ri ({son * 1.1:.1f} ball)\n\n"
        f"📝 <b>O'quvchi qo'shish (4/5)</b>\n\n"
        f"<b>1-asosiy fan</b> ({_yonalish_1fan(data['yonalish'])}) bo'yicha\n"
        f"nechta to'g'ri javob? <i>(0 – {MAX_SAVOL})</i>",
        parse_mode="HTML"
    )


@router.message(TalabaQosh.asosiy1_kutish)
async def talaba_asosiy1(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ Iltimos, 0 dan {MAX_SAVOL} gacha son kiriting.")
        return

    await state.update_data(asosiy_1=son)
    await state.set_state(TalabaQosh.asosiy2_kutish)
    data = await state.get_data()
    await message.answer(
        f"✅ 1-asosiy: <b>{son}</b> ta to'g'ri ({son * 3.1:.1f} ball)\n\n"
        f"📝 <b>O'quvchi qo'shish (5/5)</b>\n\n"
        f"<b>2-asosiy fan</b> ({_yonalish_2fan(data['yonalish'])}) bo'yicha\n"
        f"nechta to'g'ri javob? <i>(0 – {MAX_SAVOL})</i>",
        parse_mode="HTML"
    )


@router.message(TalabaQosh.asosiy2_kutish)
async def talaba_asosiy2(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ Iltimos, 0 dan {MAX_SAVOL} gacha son kiriting.")
        return

    await state.update_data(asosiy_2=son)
    data = await state.get_data()

    # Umumiy ball hisoblanadi va tasdiq so'raladi
    ball = ball_hisobla(data["majburiy"], data["asosiy_1"], son)
    await state.update_data(asosiy_2=son, ball=ball)
    await state.set_state(TalabaQosh.tasdiq_kutish)

    await message.answer(
        f"📋 <b>Ma'lumotlarni tasdiqlang:</b>\n\n"
        f"👤 Kod: <b>{data['kod']}</b>\n"
        f"🎯 Yo'nalish: <b>{data['yonalish']}</b>\n"
        f"📘 Majburiy: <b>{data['majburiy']}</b> ta → {data['majburiy'] * 1.1:.1f} ball\n"
        f"📗 1-asosiy: <b>{data['asosiy_1']}</b> ta → {data['asosiy_1'] * 3.1:.1f} ball\n"
        f"📙 2-asosiy: <b>{son}</b> ta → {son * 2.1:.1f} ball\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🏆 Umumiy ball: <b>{ball} / 189</b>",
        reply_markup=tasdiqlash_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(TalabaQosh.tasdiq_kutish, F.data.startswith("tasdiq:"))
async def talaba_tasdiq(callback: CallbackQuery, state: FSMContext):
    javob = callback.data.split(":")[1]
    data = await state.get_data()

    if javob == "ha":
        muvaffaq = talaba_qosh(
            data["kod"], data["yonalish"],
            data["majburiy"], data["asosiy_1"], data["asosiy_2"]
        )
        if muvaffaq:
            await callback.message.edit_text(
                f"✅ <b>{data['kod']}</b> kodi muvaffaqiyatli saqlandi!\n"
                f"Ball: <b>{data['ball']} / 189</b>",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"⚠️ Saqlashda xatolik. Bu kod allaqachon mavjud bo'lishi mumkin."
            )
    else:
        await callback.message.edit_text("❌ Bekor qilindi.")

    # FSM tozalanadi, lekin admin holati saqlanadi
    await state.set_state(None)
    await callback.message.answer("Keyingi amalni tanlang:", reply_markup=admin_menu_keyboard())


# ─────────────────────────────────────────
# TAHRIRLASH jarayoni (mavjud o'quvchini yangilash)
# ─────────────────────────────────────────

@router.message(F.text == "✏️ Natijani tahrirlash")
async def tahrir_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state):
        await message.answer("⛔ Ruxsat yo'q. /admin orqali kiring.")
        return

    await state.set_state(TalabaTahrir.kod_kutish)
    await message.answer("✏️ Tahrirlamoqchi bo'lgan o'quvchining <b>kodini</b> kiriting:",
                         parse_mode="HTML")


@router.message(TalabaTahrir.kod_kutish)
async def tahrir_kod(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)

    if not talaba:
        await message.answer(f"❌ <b>{kod}</b> kodi topilmadi. Qayta kiriting:", parse_mode="HTML")
        return

    await state.update_data(kod=kod, tahrir=True)
    await state.set_state(TalabaTahrir.yonalish_kutish)
    await message.answer(
        f"🔍 Topildi: <b>{kod}</b>\n"
        f"Joriy ball: <b>{talaba['umumiy_ball']} / 189</b>\n\n"
        f"Yangi yo'nalishni tanlang:",
        reply_markup=yonalish_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(TalabaTahrir.yonalish_kutish, F.data.startswith("yonalish:"))
async def tahrir_yonalish(callback: CallbackQuery, state: FSMContext):
    yonalish = callback.data.split(":", 1)[1]
    await state.update_data(yonalish=yonalish)
    await state.set_state(TalabaTahrir.majburiy_kutish)
    await callback.message.edit_text(
        f"📝 Majburiy fanlar (0–{MAX_SAVOL}) nechta to'g'ri javob?",
        parse_mode="HTML"
    )


@router.message(TalabaTahrir.majburiy_kutish)
async def tahrir_majburiy(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ 0–{MAX_SAVOL} oralig'ida son kiriting.")
        return
    await state.update_data(majburiy=son)
    await state.set_state(TalabaTahrir.asosiy1_kutish)
    await message.answer(f"📝 1-asosiy fan (0–{MAX_SAVOL}) nechta to'g'ri javob?")


@router.message(TalabaTahrir.asosiy1_kutish)
async def tahrir_asosiy1(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ 0–{MAX_SAVOL} oralig'ida son kiriting.")
        return
    await state.update_data(asosiy_1=son)
    await state.set_state(TalabaTahrir.asosiy2_kutish)
    await message.answer(f"📝 2-asosiy fan (0–{MAX_SAVOL}) nechta to'g'ri javob?")


@router.message(TalabaTahrir.asosiy2_kutish)
async def tahrir_asosiy2(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ 0–{MAX_SAVOL} oralig'ida son kiriting.")
        return

    await state.update_data(asosiy_2=son)
    data = await state.get_data()
    ball = ball_hisobla(data["majburiy"], data["asosiy_1"], son)
    await state.update_data(asosiy_2=son, ball=ball)
    await state.set_state(TalabaTahrir.tasdiq_kutish)

    await message.answer(
        f"📋 <b>Yangilangan ma'lumotlar:</b>\n\n"
        f"👤 Kod: <b>{data['kod']}</b>\n"
        f"🎯 Yo'nalish: <b>{data['yonalish']}</b>\n"
        f"📘 Majburiy: <b>{data['majburiy']}</b> → {data['majburiy'] * 1.1:.1f} ball\n"
        f"📗 1-asosiy: <b>{data['asosiy_1']}</b> → {data['asosiy_1'] * 3.1:.1f} ball\n"
        f"📙 2-asosiy: <b>{son}</b> → {son * 2.1:.1f} ball\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🏆 Yangi ball: <b>{ball} / 189</b>",
        reply_markup=tasdiqlash_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(TalabaTahrir.tasdiq_kutish, F.data.startswith("tasdiq:"))
async def tahrir_tasdiq(callback: CallbackQuery, state: FSMContext):
    javob = callback.data.split(":")[1]
    data = await state.get_data()

    if javob == "ha":
        muvaffaq = talaba_yangilash(
            data["kod"], data["yonalish"],
            data["majburiy"], data["asosiy_1"], data["asosiy_2"]
        )
        if muvaffaq:
            await callback.message.edit_text(
                f"✅ <b>{data['kod']}</b> yangilandi! Yangi ball: <b>{data['ball']} / 189</b>",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text("⚠️ Yangilashda xatolik yuz berdi.")
    else:
        await callback.message.edit_text("❌ Tahrirlash bekor qilindi.")

    await state.set_state(None)
    await callback.message.answer("Keyingi amalni tanlang:", reply_markup=admin_menu_keyboard())


# ─────────────────────────────────────────
# STATISTIKA
# ─────────────────────────────────────────

@router.message(F.text == "📊 Statistika")
async def statistika_handler(message: Message, state: FSMContext):
    if not await admin_tekshir(state):
        await message.answer("⛔ Ruxsat yo'q.")
        return

    stat = statistika()
    if not stat:
        await message.answer("📭 Hozircha hech qanday ma'lumot kiritilmagan.")
        return

    yonalish_matni = "\n".join(
        f"  • {r['yonalish']}: {r['soni']} ta o'quvchi"
        for r in stat["yonalishlar"]
    )

    await message.answer(
        f"📊 <b>Umumiy statistika</b>\n\n"
        f"👥 Jami o'quvchilar: <b>{stat['jami']}</b> ta\n"
        f"📈 O'rtacha ball: <b>{stat['ortacha']} / 189</b>\n"
        f"🥇 Eng yuqori: <b>{stat['eng_yuqori']} / 189</b>\n"
        f"🥉 Eng past: <b>{stat['eng_past']} / 189</b>\n\n"
        f"🎯 <b>Yo'nalishlar bo'yicha:</b>\n{yonalish_matni}",
        parse_mode="HTML"
    )


# ─────────────────────────────────────────
# KOD BO'YICHA QIDIRISH (admin uchun)
# ─────────────────────────────────────────

@router.message(F.text == "🔍 Kod bo'yicha qidirish")
async def admin_qidirish_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state):
        await message.answer("⛔ Ruxsat yo'q.")
        return

    await state.set_state(KodQidirish.kod_kutish)
    await message.answer("🔍 Qidirmoqchi bo'lgan o'quvchining kodini kiriting:")


@router.message(KodQidirish.kod_kutish)
async def admin_qidirish_natija(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)

    if not talaba:
        await message.answer(f"❌ <b>{kod}</b> kodi topilmadi.", parse_mode="HTML")
    else:
        await message.answer(
            f"👤 <b>Kod:</b> {talaba['kod']}\n"
            f"🎯 <b>Yo'nalish:</b> {talaba['yonalish']}\n"
            f"📘 Majburiy: {talaba['majburiy']} ta → {talaba['majburiy'] * 1.1:.1f} ball\n"
            f"📗 1-asosiy: {talaba['asosiy_1']} ta → {talaba['asosiy_1'] * 3.1:.1f} ball\n"
            f"📙 2-asosiy: {talaba['asosiy_2']} ta → {talaba['asosiy_2'] * 2.1:.1f} ball\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🏆 <b>Umumiy: {talaba['umumiy_ball']} / 189</b>",
            parse_mode="HTML"
        )

    await state.set_state(None)
    await message.answer("Keyingi amalni tanlang:", reply_markup=admin_menu_keyboard())


# ─────────────────────────────────────────
# Yordamchi funksiyalar
# ─────────────────────────────────────────

def _son_tekshir(matn: str):
    """
    Matnni butun songa aylantirishga harakat qiladi.
    0–MAX_SAVOL oralig'ida bo'lmasa None qaytaradi.
    """
    try:
        son = int(matn.strip())
        if 0 <= son <= MAX_SAVOL:
            return son
        return None
    except ValueError:
        return None


def _yonalish_1fan(yonalish: str) -> str:
    """Yo'nalish stringidan 1-fanni ajratib oladi."""
    qismlar = yonalish.split(" + ")
    return qismlar[0] if qismlar else yonalish


def _yonalish_2fan(yonalish: str) -> str:
    """Yo'nalish stringidan 2-fanni ajratib oladi."""
    qismlar = yonalish.split(" + ")
    return qismlar[1] if len(qismlar) > 1 else yonalish
