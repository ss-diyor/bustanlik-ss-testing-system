import asyncio
import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_PASSWORD, MAX_SAVOL
import pandas as pd
from certificate import CertificateGenerator
from database import (
    talaba_qosh, natija_qosh, talaba_topish, statistika, ball_hisobla,
    yonalish_ol, yonalish_qosh, yonalish_ochir, talaba_hammasi, get_all_students_for_excel,
    delete_all_data, get_all_user_ids,
    sinf_ol, sinf_qosh, sinf_ochir, talaba_songi_natija, talaba_filtrlangan,
    kalit_qosh, kalit_ol, kalit_tahrirla, kalit_holat_ozgartir, kalit_ochir,
    talaba_user_id_ol, get_setting, set_setting, get_pending_requests, update_request_status,
    get_overall_ranking, oqituvchi_qosh, oqituvchi_ol, oqituvchilar_hammasi, oqituvchi_ochir,
    get_all_in_class
)
from keyboards import (
    admin_menu_keyboard, yonalish_keyboard, tasdiqlash_keyboard,
    yonalish_boshqarish_keyboard, yonalish_ochirish_keyboard,
    sinf_keyboard, sinf_boshqarish_keyboard, sinf_ochirish_keyboard,
    kalit_boshqarish_keyboard, kalit_actions_keyboard, kalit_yonalish_tanlash_keyboard,
    oquvchilar_filtrlash_keyboard, sinf_tanlash_keyboard, yonalish_tanlash_keyboard, filter_actions_keyboard,
    settings_keyboard, request_actions_keyboard, ranking_keyboard, sinf_tanlash_ranking_keyboard,
    oqituvchi_boshqarish_keyboard, oqituvchi_menu_keyboard, oqituvchi_ochirish_keyboard
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
    sinf_kutish = State()
    ismlar_kutish = State()
    majburiy_kutish = State()
    asosiy1_kutish = State()
    asosiy2_kutish = State()
    tasdiq_kutish = State()

class ExcelImport(StatesGroup):
    fayl_kutish = State()

class KalitBoshqar(StatesGroup):
    nomi_kutish = State()
    kalit_kutish = State()
    edit_kalit_kutish = State()
    yonalish_nomi_kutish = State()   # Yo'nalishga kalit: test nomi
    yonalish_kalit_kutish = State()  # Yo'nalishga kalit: kalitlar matni

class KodQidirish(StatesGroup):
    kod_kutish = State()

class YonalishBoshqar(StatesGroup):
    nomi_kutish = State()

class SinfBoshqar(StatesGroup):
    nomi_kutish = State()

class Broadcast(StatesGroup):
    xabar_kutish = State()

class MurojaatJavob(StatesGroup):
    javob_kutish = State()

class ConfirmDelete(StatesGroup):
    tasdiqlash_kutish = State()

class OqituvchiQosh(StatesGroup):
    user_id_kutish = State()
    ismlar_kutish = State()
    sinf_kutish = State()

class NatijaTahrirlash(StatesGroup):
    kod_kutish = State()
    majburiy_kutish = State()
    asosiy1_kutish = State()
    asosiy2_kutish = State()

# ─────────────────────────────────────────
# Yordamchi funksiyalar
# ─────────────────────────────────────────

async def is_admin(message: Message, state: FSMContext):
    data = await state.get_data()
    return data.get("admin") is True

async def admin_tekshir(state: FSMContext) -> bool:
    data = await state.get_data()
    return data.get("admin") is True

def is_admin_id(user_id: int) -> bool:
    from config import ADMIN_IDS
    return user_id in ADMIN_IDS

def _son_tekshir(text: str):
    try:
        son = int(text)
        if 0 <= son <= MAX_SAVOL:
            return son
    except ValueError:
        pass
    return None

def _generate_certificate_file(cert_gen, ismlar, ball, sana, kod):
    """Sertifikatni alohida executor'da generatsiya qilish uchun."""
    return cert_gen.generate(ismlar, ball, sana, kod)

async def bildirishnoma_yuborish(bot: Bot, talaba_kod: str, natija: dict, talaba: dict):
    """
    Talabaning Telegram user_id si bo'lsa, yangi natija haqida xabar yuboradi.
    Sertifikat ham generatsiya qilinadi.
    """
    user_id = talaba_user_id_ol(talaba_kod)
    if not user_id:
        return  # Talaba profilini ulamagan — bildirishnoma yo'q

    from database import get_student_rank, get_score_difference
    try:
        ranks = get_student_rank(talaba_kod)
        diff = get_score_difference(talaba_kod)
    except Exception as e:
        print(f"Rank/Diff error: {e}")
        ranks = {'class': None, 'overall': None}
        diff = None
    
    foiz = round((natija['umumiy_ball'] / 189) * 100, 1)
    
    status_text = ""
    if ranks['class']:
        status_text = f"📍 Siz sinfda <b>{ranks['class']}-o'rindasiz</b>."
    
    diff_text = ""
    if diff is not None:
        if diff > 0:
            diff_text = f"\n📈 Natijangiz <b>+{diff} ballga</b> yaxshilandi! Tabriklaymiz! 🎉"
        elif diff < 0:
            diff_text = f"\n📉 Natijangiz <b>{diff} ballga</b> o'zgardi. Keyingi safar yanada yaxshiroq bo'ladi! 💪"
        else:
            diff_text = "\n⏺ Natijangiz o'zgarmadi."

    matn = (
        f"🔔 <b>Yangi test natijangiz kiritildi!</b>\n\n"
        f"👤 Ism: <b>{talaba['ismlar']}</b>\n"
        f"🆔 Kod: <b>{talaba['kod']}</b>\n\n"
        f"📊 <b>Natijalar:</b>\n"
        f"  📘 Majburiy: {natija['majburiy']}/30 → <b>{natija['majburiy'] * 1.1:.1f}</b> ball\n"
        f"  📗 1-asosiy: {natija['asosiy_1']}/30 → <b>{natija['asosiy_1'] * 3.1:.1f}</b> ball\n"
        f"  📙 2-asosiy: {natija['asosiy_2']}/30 → <b>{natija['asosiy_2'] * 2.1:.1f}</b> ball\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Umumiy ball: {natija['umumiy_ball']} / 189</b>\n"
        f"📈 Foiz: <b>{foiz}%</b>\n\n"
        f"{status_text}{diff_text}\n\n"
        f"📜 Quyida sizning natijangiz aks etgan sertifikat biriktirilgan."
    )
    
    # Sertifikat yaratish (Blocking bo'lgani uchun executor ishlatamiz)
    try:
        cert_gen = CertificateGenerator()
        sana = str(natija.get('test_sanasi', 'Noaniq'))[:10]
        
        loop = asyncio.get_event_loop()
        cert_path = await loop.run_in_executor(None, _generate_certificate_file, cert_gen, talaba['ismlar'], natija['umumiy_ball'], sana, talaba['kod'])
        
        await bot.send_document(
            user_id, 
            FSInputFile(cert_path), 
            caption=matn, 
            parse_mode="HTML"
        )
        # Sertifikatni yuborgandan keyin o'chirib tashlaymiz
        if os.path.exists(cert_path):
            os.remove(cert_path)
    except Exception as e:
        # Agar sertifikatda xato bo'lsa, faqat matnni yuboramiz
        try:
            await bot.send_message(user_id, matn, parse_mode="HTML")
        except Exception:
            pass

# ─────────────────────────────────────────
# /admin va Kirish
# ─────────────────────────────────────────

@router.message(F.text == "/admin")
async def admin_start(message: Message, state: FSMContext):
    if await admin_tekshir(state):
        await message.answer("✅ Siz allaqachon admin rejimidasiz.", reply_markup=admin_menu_keyboard())
        return
    await state.set_state(AdminLogin.parol_kutish)
    await message.answer("🔐 Admin paroli kiriting:")


@router.message(AdminLogin.parol_kutish)
async def parol_tekshir(message: Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASSWORD:
        await state.update_data(admin=True)
        await state.set_state(None)
        await message.answer("✅ Xush kelibsiz, admin!", reply_markup=admin_menu_keyboard())
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
    await message.answer("Yo'nalishlarni boshqarish menyusi:", reply_markup=yonalish_boshqarish_keyboard())


@router.callback_query(F.data.startswith("yonalish_boshqar:"))
async def yonalish_boshqar_actions(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "ro'yxat":
        yonalishlar = yonalish_ol()
        if not yonalishlar:
            text = "⚠️ Hozircha yo'nalishlar yo'q."
        else:
            text = "📋 <b>Mavjud yo'nalishlar ro'yxati:</b>\n\n"
            for i, y in enumerate(yonalishlar, 1):
                text += f"{i}. {y}\n"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=yonalish_boshqarish_keyboard())

    elif action == "qosh":
        await state.set_state(YonalishBoshqar.nomi_kutish)
        await callback.message.edit_text("📝 Yangi yo'nalish nomini kiriting:\n(Masalan: Matematika + Fizika)")

    elif action == "ochir":
        await callback.message.edit_text("❌ O'chirmoqchi bo'lgan yo'nalishni tanlang:",
                                         reply_markup=yonalish_ochirish_keyboard())

    elif action == "orqaga":
        await state.set_state(None)
        await callback.message.edit_text("Yo'nalishlarni boshqarish menyusi:",
                                         reply_markup=yonalish_boshqarish_keyboard())


@router.message(YonalishBoshqar.nomi_kutish)
async def yonalish_nomi_saqla(message: Message, state: FSMContext):
    nomi = message.text.strip()
    if yonalish_qosh(nomi):
        await message.answer(f"✅ Yangi yo'nalish qo'shildi: <b>{nomi}</b>",
                             parse_mode="HTML", reply_markup=admin_menu_keyboard())
    else:
        await message.answer("❌ Bu yo'nalish allaqachon mavjud.")
    await state.set_state(None)


@router.callback_query(F.data.startswith("yonalish_ochir:"))
async def yonalish_ochir_tasdiq(callback: CallbackQuery):
    nomi = callback.data.split(":")[1]
    yonalish_ochir(nomi)
    await callback.answer(f"✅ {nomi} o'chirildi")
    await callback.message.edit_text("❌ O'chirmoqchi bo'lgan yo'nalishni tanlang:",
                                     reply_markup=yonalish_ochirish_keyboard())

# ─────────────────────────────────────────
# Sinflarni boshqarish
# ─────────────────────────────────────────

@router.message(F.text == "🏫 Sinflarni boshqarish")
async def sinf_boshqar_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await message.answer("Sinflarni boshqarish menyusi:", reply_markup=sinf_boshqarish_keyboard())


@router.callback_query(F.data.startswith("sinf_boshqar:"))
async def sinf_boshqar_actions(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "ro'yxat":
        sinflar = sinf_ol()
        if not sinflar:
            text = "⚠️ Hozircha sinflar yo'q."
        else:
            text = "📋 <b>Mavjud sinflar ro'yxati:</b>\n\n"
            for i, s in enumerate(sinflar, 1):
                text += f"{i}. {s}\n"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=sinf_boshqarish_keyboard())

    elif action == "qosh":
        await state.set_state(SinfBoshqar.nomi_kutish)
        await callback.message.edit_text("📝 Yangi sinf nomini kiriting:\n(Masalan: 11-A)")

    elif action == "ochir":
        await callback.message.edit_text("❌ O'chirmoqchi bo'lgan sinfni tanlang:",
                                         reply_markup=sinf_ochirish_keyboard())

    elif action == "orqaga":
        await state.set_state(None)
        await callback.message.edit_text("Sinflarni boshqarish menyusi:",
                                         reply_markup=sinf_boshqarish_keyboard())


@router.message(SinfBoshqar.nomi_kutish)
async def sinf_nomi_saqla(message: Message, state: FSMContext):
    nomi = message.text.strip()
    if sinf_qosh(nomi):
        await message.answer(f"✅ Yangi sinf qo'shildi: <b>{nomi}</b>",
                             parse_mode="HTML", reply_markup=admin_menu_keyboard())
    else:
        await message.answer("❌ Bu sinf allaqachon mavjud.")
    await state.set_state(None)


@router.callback_query(F.data.startswith("sinf_ochir:"))
async def sinf_ochir_tasdiq(callback: CallbackQuery):
    nomi = callback.data.split(":")[1]
    sinf_ochir(nomi)
    await callback.answer(f"✅ {nomi} o'chirildi")
    await callback.message.edit_text("❌ O'chirmoqchi bo'lgan sinfni tanlang:",
                                     reply_markup=sinf_ochirish_keyboard())

# ─────────────────────────────────────────
# Test kalitlarini boshqarish
# ─────────────────────────────────────────

@router.message(F.text == "🔑 Test kalitlarini boshqarish")
async def kalit_boshqar_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await message.answer("Test kalitlarini boshqarish menyusi:", reply_markup=kalit_boshqarish_keyboard())


@router.callback_query(F.data.startswith("kalit_boshqar:"))
async def kalit_boshqar_actions(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "ro'yxat":
        kalitlar = kalit_ol()
        if not kalitlar:
            await callback.message.edit_text("⚠️ Hozircha test kalitlari yo'q.", reply_markup=kalit_boshqarish_keyboard())
        else:
            text = "📋 <b>Mavjud test kalitlari:</b>\n\n"
            for k in kalitlar:
                text += f"📌 {k['test_nomi']} ({k['holat']})\n"
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kalit_boshqarish_keyboard())

    elif action == "qosh":
        await state.set_state(KalitBoshqar.nomi_kutish)
        await callback.message.edit_text("📝 Yangi test nomini kiriting:")

    elif action == "yonalish_qosh":
        await state.set_state(KalitBoshqar.yonalish_nomi_kutish)
        await callback.message.edit_text("📝 Yo'nalishga tegishli test nomini kiriting:")

    elif action == "ochir":
        kalitlar = kalit_ol()
        if not kalitlar:
            await callback.answer("O'chirish uchun testlar yo'q")
            return
        
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        for k in kalitlar:
            kb.inline_keyboard.append([InlineKeyboardButton(text=f"❌ {k['test_nomi']}", callback_data=f"kalit_del:{k['test_nomi']}")])
        kb.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="kalit_boshqar:orqaga")])
        
        await callback.message.edit_text("O'chirmoqchi bo'lgan testni tanlang:", reply_markup=kb)

    elif action == "orqaga":
        await state.set_state(None)
        await callback.message.edit_text("Test kalitlarini boshqarish menyusi:", reply_markup=kalit_boshqarish_keyboard())


@router.message(KalitBoshqar.nomi_kutish)
async def kalit_nomi_saqla(message: Message, state: FSMContext):
    await state.update_data(test_nomi=message.text.strip())
    await state.set_state(KalitBoshqar.kalit_kutish)
    await message.answer("📝 Test kalitlarini kiriting (Masalan: ABCD...):")


@router.message(KalitBoshqar.kalit_kutish)
async def kalit_matni_saqla(message: Message, state: FSMContext):
    data = await state.get_data()
    if kalit_qosh(data['test_nomi'], message.text.strip()):
        await message.answer(f"✅ {data['test_nomi']} kalitlari saqlandi!", reply_markup=admin_menu_keyboard())
    else:
        await message.answer("❌ Xatolik yuz berdi yoki bu test nomi allaqachon mavjud.")
    await state.set_state(None)


@router.message(KalitBoshqar.yonalish_nomi_kutish)
async def kalit_yonalish_nomi(message: Message, state: FSMContext):
    await state.update_data(test_nomi=message.text.strip())
    await state.set_state(KalitBoshqar.yonalish_kalit_kutish)
    await message.answer("📝 Test kalitlarini kiriting:")


@router.message(KalitBoshqar.yonalish_kalit_kutish)
async def kalit_yonalish_kalit(message: Message, state: FSMContext):
    await state.update_data(kalitlar=message.text.strip())
    await message.answer("🎯 Bu test qaysi yo'nalish uchun?", reply_markup=kalit_yonalish_tanlash_keyboard())


@router.callback_query(F.data.startswith("kalit_yonalish:"))
async def kalit_yonalish_final(callback: CallbackQuery, state: FSMContext):
    yonalish = callback.data.split(":")[1]
    if yonalish == "null": yonalish = None
    
    data = await state.get_data()
    if kalit_qosh(data['test_nomi'], data['kalitlar'], yonalish):
        await callback.message.edit_text(f"✅ {data['test_nomi']} ({yonalish or 'Umumiy'}) saqlandi!")
    else:
        await callback.message.edit_text("❌ Xatolik yuz berdi.")
    await state.set_state(None)


@router.callback_query(F.data.startswith("kalit_del:"))
async def kalit_delete(callback: CallbackQuery):
    test_nomi = callback.data.split(":", 1)[1]
    kalit_ochir(test_nomi)
    await callback.answer(f"✅ {test_nomi} o'chirildi")
    await callback.message.edit_text("Test kalitlarini boshqarish menyusi:",
                                     reply_markup=kalit_boshqarish_keyboard())

# ─────────────────────────────────────────
# O'quvchi QO'SHISH (Bildirishnoma bilan)
# ─────────────────────────────────────────

@router.message(F.text == "➕ O'quvchi qo'shish")
async def talaba_qosh_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await state.set_state(TalabaQosh.kod_kutish)
    await message.answer("📝 O'quvchining shaxsiy <b>kodini</b> kiriting:", parse_mode="HTML")


@router.message(TalabaQosh.kod_kutish)
async def talaba_kod(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    await state.update_data(kod=kod)
    await state.set_state(TalabaQosh.yonalish_kutish)
    await message.answer(f"✅ Kod: <b>{kod}</b>\n\nYo'nalishni tanlang:",
                         reply_markup=yonalish_keyboard(), parse_mode="HTML")


@router.callback_query(TalabaQosh.yonalish_kutish, F.data.startswith("yonalish:"))
async def talaba_yonalish(callback: CallbackQuery, state: FSMContext):
    yonalish = callback.data.split(":", 1)[1]
    await state.update_data(yonalish=yonalish)
    await state.set_state(TalabaQosh.sinf_kutish)
    await callback.message.edit_text(f"✅ Yo'nalish: <b>{yonalish}</b>\n\nSinfni tanlang:",
                                     reply_markup=sinf_keyboard(), parse_mode="HTML")


@router.callback_query(TalabaQosh.sinf_kutish, F.data.startswith("sinf:"))
async def talaba_sinf(callback: CallbackQuery, state: FSMContext):
    sinf = callback.data.split(":", 1)[1]
    await state.update_data(sinf=sinf)
    await state.set_state(TalabaQosh.ismlar_kutish)
    await callback.message.edit_text(f"✅ Sinf: <b>{sinf}</b>\n\nO'quvchining ism-sharifini kiriting:",
                                     parse_mode="HTML")


@router.message(TalabaQosh.ismlar_kutish)
async def talaba_ismlar(message: Message, state: FSMContext):
    await state.update_data(ismlar=message.text.strip())
    await state.set_state(TalabaQosh.majburiy_kutish)
    await message.answer(
        f"✅ Ism: <b>{message.text.strip()}</b>\n\nMajburiy fanlar (0-{MAX_SAVOL}) to'g'ri javoblar:",
        parse_mode="HTML"
    )


@router.message(TalabaQosh.majburiy_kutish)
async def talaba_majburiy(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ 0 dan {MAX_SAVOL} gacha son kiriting.")
        return
    await state.update_data(majburiy=son)
    await state.set_state(TalabaQosh.asosiy1_kutish)
    await message.answer(f"✅ Majburiy: <b>{son}</b> ta\n\n1-asosiy fan (0-{MAX_SAVOL}) to'g'ri javoblar:",
                         parse_mode="HTML")


@router.message(TalabaQosh.asosiy1_kutish)
async def talaba_asosiy1(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ 0 dan {MAX_SAVOL} gacha son kiriting.")
        return
    await state.update_data(asosiy_1=son)
    await state.set_state(TalabaQosh.asosiy2_kutish)
    await message.answer(f"✅ 1-asosiy: <b>{son}</b> ta\n\n2-asosiy fan (0-{MAX_SAVOL}) to'g'ri javoblar:",
                         parse_mode="HTML")


@router.message(TalabaQosh.asosiy2_kutish)
async def talaba_asosiy2(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ 0 dan {MAX_SAVOL} gacha son kiriting.")
        return
    data = await state.get_data()
    ball = ball_hisobla(data["majburiy"], data["asosiy_1"], son)
    await state.update_data(asosiy_2=son, ball=ball)
    await state.set_state(TalabaQosh.tasdiq_kutish)
    await message.answer(
        f"📋 <b>Tasdiqlang:</b>\n"
        f"Kod: <b>{data['kod']}</b>\n"
        f"Ism: <b>{data['ismlar']}</b>\n"
        f"Sinf: <b>{data['sinf']}</b>\n"
        f"Yo'nalish: <b>{data['yonalish']}</b>\n"
        f"Ball: <b>{ball}</b>",
        parse_mode="HTML",
        reply_markup=tasdiqlash_keyboard()
    )


@router.callback_query(TalabaQosh.tasdiq_kutish, F.data.startswith("tasdiq:"))
async def talaba_tasdiq(callback: CallbackQuery, state: FSMContext):
    javob = callback.data.split(":")[1]
    if javob == "ha":
        data = await state.get_data()
        if not talaba_topish(data["kod"]):
            talaba_qosh(data["kod"], data["yonalish"], data["sinf"], data["ismlar"])

        natija_qosh(data["kod"], data["majburiy"], data["asosiy_1"], data["asosiy_2"])

        # Talabaga bildirishnoma yuborish
        talaba = talaba_topish(data["kod"])
        from database import talaba_songi_natija
        yangi_natija = talaba_songi_natija(data["kod"])
        
        # Bildirishnomani async fon rejimida yuboramiz, admin javobini kutib qolmasligi uchun
        if talaba and yangi_natija:
            asyncio.create_task(bildirishnoma_yuborish(callback.bot, data["kod"], yangi_natija, talaba))

        await callback.message.edit_text(f"✅ {data['kod']} natijasi saqlandi!")
    else:
        await callback.message.edit_text("❌ Bekor qilindi.")
    await state.set_state(None)
    await callback.message.answer("Keyingi amal:", reply_markup=admin_menu_keyboard())

# ─────────────────────────────────────────
# Natijani Tahrirlash
# ─────────────────────────────────────────

@router.message(F.text == "✏️ Natijani tahrirlash")
async def natija_tahrirlash_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await state.set_state(NatijaTahrirlash.kod_kutish)
    await message.answer("🔍 Tahrirlash uchun o'quvchi <b>kodini</b> kiriting:", parse_mode="HTML")


@router.message(NatijaTahrirlash.kod_kutish)
async def natija_tahrirlash_kod(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer(f"❌ <b>{kod}</b> topilmadi.", parse_mode="HTML")
        await state.set_state(None)
        return
    await state.update_data(tahrir_kod=kod)
    await state.set_state(NatijaTahrirlash.majburiy_kutish)
    await message.answer(
        f"✅ Topildi: <b>{talaba['ismlar']}</b>\n\n"
        f"Yangi majburiy fan natijalari (0-{MAX_SAVOL}):",
        parse_mode="HTML"
    )


@router.message(NatijaTahrirlash.majburiy_kutish)
async def natija_tahrirlash_majburiy(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ 0 dan {MAX_SAVOL} gacha son kiriting.")
        return
    await state.update_data(t_majburiy=son)
    await state.set_state(NatijaTahrirlash.asosiy1_kutish)
    await message.answer(f"✅ Majburiy: <b>{son}</b>\n\n1-asosiy fan (0-{MAX_SAVOL}):", parse_mode="HTML")


@router.message(NatijaTahrirlash.asosiy1_kutish)
async def natija_tahrirlash_asosiy1(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ 0 dan {MAX_SAVOL} gacha son kiriting.")
        return
    await state.update_data(t_asosiy1=son)
    await state.set_state(NatijaTahrirlash.asosiy2_kutish)
    await message.answer(f"✅ 1-asosiy: <b>{son}</b>\n\n2-asosiy fan (0-{MAX_SAVOL}):", parse_mode="HTML")


@router.message(NatijaTahrirlash.asosiy2_kutish)
async def natija_tahrirlash_asosiy2(message: Message, state: FSMContext):
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer(f"❌ 0 dan {MAX_SAVOL} gacha son kiriting.")
        return
    data = await state.get_data()
    natija_qosh(data["tahrir_kod"], data["t_majburiy"], data["t_asosiy1"], son)

    # Bildirishnoma
    talaba = talaba_topish(data["tahrir_kod"])
    from database import talaba_songi_natija
    yangi_natija = talaba_songi_natija(data["tahrir_kod"])
    if talaba and yangi_natija:
        asyncio.create_task(bildirishnoma_yuborish(message.bot, data["tahrir_kod"], yangi_natija, talaba))

    ball = ball_hisobla(data["t_majburiy"], data["t_asosiy1"], son)
    await message.answer(
        f"✅ <b>{data['tahrir_kod']}</b> uchun yangi natija saqlandi!\n"
        f"🏆 Yangi ball: <b>{ball}</b>",
        parse_mode="HTML", reply_markup=admin_menu_keyboard()
    )
    await state.set_state(None)

# ─────────────────────────────────────────
# Exceldan IMPORT (Bildirishnoma bilan)
# ─────────────────────────────────────────

@router.message(F.text == "📥 Exceldan import")
async def excel_import_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await state.set_state(ExcelImport.fayl_kutish)
    await message.answer(
        "📥 <b>Excel faylini yuboring.</b>\n\n"
        "Fayl ustunlari tartibi:\n"
        "<code>Kod | Ism | Sinf | Yo'nalish | Majburiy | Asosiy1 | Asosiy2</code>",
        parse_mode="HTML"
    )

@router.message(ExcelImport.fayl_kutish, F.document)
async def excel_import_process(message: Message, state: FSMContext):
    file_id = message.document.file_id
    file = await message.bot.get_file(file_id)
    local_path = f"import_{message.from_user.id}.xlsx"
    await message.bot.download_file(file.file_path, local_path)

    try:
        df = pd.read_excel(local_path)
        count = 0
        errors = 0

        for _, row in df.iterrows():
            try:
                kod = str(row[0]).strip().upper()
                ismlar = str(row[1]).strip()
                sinf = str(row[2]).strip()
                yonalish = str(row[3]).strip()
                majburiy = int(row[4])
                asosiy1 = int(row[5])
                asosiy2 = int(row[6])

                if not talaba_topish(kod):
                    talaba_qosh(kod, yonalish, sinf, ismlar)

                if natija_qosh(kod, majburiy, asosiy1, asosiy2):
                    count += 1
                    # Bildirishnoma
                    talaba = talaba_topish(kod)
                    from database import talaba_songi_natija
                    yangi_natija = talaba_songi_natija(kod)
                    if talaba and yangi_natija:
                        asyncio.create_task(bildirishnoma_yuborish(message.bot, kod, yangi_natija, talaba))
                    await asyncio.sleep(0.05)  # Telegram rate limit
                else:
                    errors += 1
            except Exception:
                errors += 1

        await message.answer(
            f"✅ Import yakunlandi!\n\n"
            f"✔️ Muvaffaqiyatli: <b>{count}</b> ta\n"
            f"❌ Xatoliklar: <b>{errors}</b> ta",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ Faylni o'qishda xatolik: {e}")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

    await state.set_state(None)

# ─────────────────────────────────────────
# Statistika
# ─────────────────────────────────────────

@router.message(F.text == "📊 Statistika")
async def admin_statistika(message: Message, state: FSMContext):
    s = statistika()
    if not s:
        await message.answer("⚠️ Ma'lumotlar yetarli emas.")
        return
    
    text = (
        f"📊 <b>Umumiy statistika:</b>\n\n"
        f"👥 Jami o'quvchilar: <b>{s['jami']}</b>\n"
        f"📈 O'rtacha ball: <b>{s['ortacha']}</b>\n"
        f"🔝 Eng yuqori ball: <b>{s['eng_yuqori']}</b>\n"
        f"🔻 Eng past ball: <b>{s['eng_past']}</b>"
    )
    from student import stats_keyboard
    await message.answer(text, parse_mode="HTML", reply_markup=stats_keyboard())

@router.message(F.text == "🏆 Reyting")
async def admin_ranking(message: Message, state: FSMContext):
    if not is_admin_id(message.from_user.id):
        return
    await message.answer("🏆 <b>Reyting bo'limi:</b>", parse_mode="HTML", reply_markup=ranking_keyboard(is_admin=True))

@router.callback_query(F.data == "ranking:select_class")
async def admin_ranking_select_class(callback: CallbackQuery):
    await callback.message.edit_text("🏫 Reytingni ko'rish uchun sinfni tanlang:", reply_markup=sinf_tanlash_ranking_keyboard())

@router.callback_query(F.data == "ranking:top_by_classes")
async def admin_ranking_top_by_classes(callback: CallbackQuery):
    from keyboards import sinf_prefix_tanlash_keyboard
    await callback.message.edit_text("📊 Qaysi sinflar bo'yicha Top reytingni ko'rmoqchisiz?", reply_markup=sinf_prefix_tanlash_keyboard())

@router.callback_query(F.data.startswith("ranking:top_prefix:"))
async def admin_ranking_view_prefix(callback: CallbackQuery):
    prefix = callback.data.split(":")[2]
    from database import get_overall_ranking
    top50 = get_overall_ranking(sinf_prefix=prefix)
    
    if not top50:
        await callback.answer(f"⚠️ {prefix}-sinflarda natijalar yo'q.")
        return
        
    text = f"🏆 <b>{prefix}-sinflar bo'yicha Top 50:</b>\n\n"
    for i, t in enumerate(top50, 1):
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{emoji} {t['ismlar']} ({t['sinf']}) — <b>{t['umumiy_ball']}</b>\n"
    
    from keyboards import sinf_prefix_tanlash_keyboard
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=sinf_prefix_tanlash_keyboard())

@router.callback_query(F.data.startswith("ranking:view_class:"))
async def admin_ranking_view_class(callback: CallbackQuery):
    sinf = callback.data.split(":")[2]
    from database import get_all_in_class
    talabalar = get_all_in_class(sinf)
    
    if not talabalar:
        await callback.answer(f"⚠️ {sinf} sinfida natijalar yo'q.")
        return
        
    text = f"🏆 <b>{sinf} sinf reytingi:</b>\n\n"
    for i, t in enumerate(talabalar, 1):
        text += f"{i}. {t['ismlar']} — <b>{t['umumiy_ball']}</b>\n"
    
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=sinf_tanlash_ranking_keyboard())

@router.callback_query(F.data == "ranking:back_admin")
async def admin_ranking_back(callback: CallbackQuery):
    await callback.message.edit_text("🏆 <b>Reyting bo'limi:</b>", parse_mode="HTML", reply_markup=ranking_keyboard(is_admin=True))

@router.message(F.text == "⚙️ Sozlamalar")
async def admin_settings(message: Message, state: FSMContext):
    ranking_enabled = get_setting('ranking_enabled', 'True')
    stats_enabled = get_setting('stats_enabled', 'True')
    await message.answer("⚙️ <b>Bot sozlamalari:</b>\n\nO'quvchilar uchun funksiyalarni yoqish yoki o'chirish:", 
                         parse_mode="HTML", 
                         reply_markup=settings_keyboard(ranking_enabled, stats_enabled))

@router.callback_query(F.data.startswith("toggle_setting:"))
async def toggle_setting_handler(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state): return
    key = callback.data.split(":")[1]
    current = get_setting(key, 'True')
    new_value = 'False' if current == 'True' else 'True'
    set_setting(key, new_value)
    
    ranking_enabled = get_setting('ranking_enabled', 'True')
    stats_enabled = get_setting('stats_enabled', 'True')
    await callback.message.edit_reply_markup(reply_markup=settings_keyboard(ranking_enabled, stats_enabled))
    
    # O'zgarishni tasdiqlash uchun xabar yuboramiz va yangi menyuni taqdim etamiz
    status = "yoqildi" if new_value == "True" else "o'chirildi"
    setting_name = "Reyting" if key == "ranking_enabled" else "Statistika"
    await callback.message.answer(f"✅ {setting_name} funksiyasi {status}.")
    await callback.answer()

@router.message(F.text == "🔔 So'rovlar", is_admin)
async def admin_requests(message: Message, state: FSMContext):
    requests = get_pending_requests()
    if not requests:
        await message.answer("📭 Hozircha yangi so'rovlar yo'q.")
        return
    
    for req in requests:
        text = (
            f"🔔 <b>Yangi kirish so'rovi!</b>\n\n"
            f"👤 O'quvchi: <b>{req['ismlar']}</b>\n"
            f"🏫 Sinf: <b>{req['sinf']}</b>\n"
            f"🎯 Yo'nalish: <b>{req.get('yonalish', 'Noma' + chr(39) + 'lum')}</b>\n"
            f"🆔 Kod: <code>{req['talaba_kod']}</code>\n"
            f"👤 Telegram ID: <code>{req['user_id']}</code>"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=request_actions_keyboard(req['id'], req['user_id']))

@router.callback_query(F.data.startswith("request_action:"))
async def request_action_handler(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state): return
    data_parts = callback.data.split(":")
    action = data_parts[1]
    target_id = int(data_parts[2]) # request_id yoki user_id bo'lishi mumkin
    
    from database import get_connection, release_connection, revoke_access_by_user
    from datetime import datetime, timedelta

    if action == "revoke":
        revoke_access_by_user(target_id)
        await callback.answer("🚫 Ruxsat qaytarib olindi")
        await callback.message.edit_text(f"🚫 Foydalanuvchining (ID: {target_id}) barcha ruxsatlari bekor qilindi.")
        try:
            await callback.bot.send_message(target_id, "🚫 Admin sizdan umumiy reytingni ko'rish ruxsatini qaytarib oldi.")
        except Exception: pass
        return

    # So'rov ma'lumotlarini olish
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM access_requests WHERE id = %s", (target_id,))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    
    if not row:
        await callback.answer("⚠️ So'rov topilmadi.")
        return

    user_id = row[0]
    expires_at = None
    time_text = "cheksiz vaqtga"

    if action == "approve_5m":
        expires_at = datetime.now() + timedelta(minutes=5)
        time_text = "5 daqiqaga"
        update_request_status(target_id, 'approved', expires_at)
    elif action == "approve_30m":
        expires_at = datetime.now() + timedelta(minutes=30)
        time_text = "30 daqiqaga"
        update_request_status(target_id, 'approved', expires_at)
    elif action == "approve_1h":
        expires_at = datetime.now() + timedelta(hours=1)
        time_text = "1 soatga"
        update_request_status(target_id, 'approved', expires_at)
    elif action == "reject":
        update_request_status(target_id, 'rejected')
        await callback.answer("❌ Rad etildi")
        await callback.message.edit_text(f"❌ Foydalanuvchining (ID: {user_id}) so'rovi rad etildi.")
        try:
            await callback.bot.send_message(user_id, "❌ Admin umumiy reytingni ko'rish so'rovingizni rad etdi.")
        except Exception: pass
        return
    else: # Eski 'approve' tugmasi uchun (agar qolgan bo'lsa)
        update_request_status(target_id, 'approved', None)

    await callback.answer(f"✅ Ruxsat berildi ({time_text})")
    await callback.message.edit_text(
        f"✅ Foydalanuvchiga (ID: {user_id}) umumiy reytingni ko'rishga <b>{time_text}</b> ruxsat berildi.",
        parse_mode="HTML",
        reply_markup=request_actions_keyboard(target_id, user_id)
    )
    try:
        await callback.bot.send_message(user_id, f"✅ Admin umumiy reytingni ko'rishga <b>{time_text}</b> ruxsat berdi! Endi '🏆 Reyting' menyusi orqali 'Umumiy Top' ni ko'rishingiz mumkin.", parse_mode="HTML")
    except Exception: pass


@router.message(F.text == "📋 O'quvchilar ro'yxati")
async def students_list(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await message.answer("📋 O'quvchilar ro'yxatini ko'rish usulini tanlang:", reply_markup=oquvchilar_filtrlash_keyboard())

@router.callback_query(F.data.startswith("filter_type:"))
async def filter_type_process(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    
    if action == "sinf":
        await callback.message.edit_text("🏫 Sinfni tanlang:", reply_markup=sinf_tanlash_keyboard())
    elif action == "yonalish":
        await callback.message.edit_text("🎯 Yo'nalishni tanlang:", reply_markup=yonalish_tanlash_keyboard())
    elif action == "hammasi":
        talabalar = talaba_hammasi()
        if not talabalar:
            await callback.answer("⚠️ O'quvchilar topilmadi.")
            return
        text = "📋 <b>Barcha o'quvchilar:</b>\n\n"
        for i, t in enumerate(talabalar[:50], 1):
            text += f"{i}. {t['kod']} | {t['ismlar']} | {t['sinf']} | <b>{t['umumiy_ball'] or 0}</b>\n"
        if len(talabalar) > 50:
            text += f"\n<i>...va yana {len(talabalar)-50} ta o'quvchi.</i>"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=filter_actions_keyboard("all", "all"))
    elif action == "back":
        await callback.message.edit_text("📋 O'quvchilar ro'yxatini ko'rish usulini tanlang:", reply_markup=oquvchilar_filtrlash_keyboard())
    elif action == "orqaga":
        await callback.message.delete()

@router.callback_query(F.data.startswith("filter_sinf:"))
async def filter_sinf_process(callback: CallbackQuery):
    sinf = callback.data.split(":")[1]
    talabalar = talaba_filtrlangan(sinf=sinf)
    if not talabalar:
        await callback.answer(f"⚠️ {sinf} sinfida o'quvchilar yo'q.")
        return
    text = f"📋 <b>{sinf} sinfi o'quvchilari:</b>\n\n"
    for i, t in enumerate(talabalar[:50], 1):
        text += f"{i}. {t['kod']} | {t['ismlar']} | <b>{t['umumiy_ball'] or 0}</b>\n"
    if len(talabalar) > 50:
        text += f"\n<i>...va yana {len(talabalar)-50} ta o'quvchi.</i>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=filter_actions_keyboard("sinf", sinf))

@router.callback_query(F.data.startswith("filter_yon:"))
async def filter_yon_process(callback: CallbackQuery):
    yonalish = callback.data.split(":")[1]
    talabalar = talaba_filtrlangan(yonalish=yonalish)
    if not talabalar:
        await callback.answer(f"⚠️ Bu yo'nalishda o'quvchilar yo'q.")
        return
    text = f"🎯 <b>{yonalish} yo'nalishi:</b>\n\n"
    for i, t in enumerate(talabalar[:50], 1):
        text += f"{i}. {t['kod']} | {t['ismlar']} | {t['sinf']} | <b>{t['umumiy_ball'] or 0}</b>\n"
    if len(talabalar) > 50:
        text += f"\n<i>...va yana {len(talabalar)-50} ta o'quvchi.</i>"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=filter_actions_keyboard("yonalish", yonalish))

@router.callback_query(F.data.startswith("filter_excel:"))
async def filter_excel_process(callback: CallbackQuery):
    parts = callback.data.split(":")
    f_type = parts[1]
    f_val = parts[2]
    
    if f_type == "all":
        data = talaba_hammasi()
        caption = "📊 Barcha o'quvchilar natijalari"
    elif f_type == "sinf":
        data = talaba_filtrlangan(sinf=f_val)
        caption = f"📊 {f_val} sinfi natijalari"
    elif f_type == "yonalish":
        data = talaba_filtrlangan(yonalish=f_val)
        caption = f"📊 {f_val} yo'nalishi natijalari"
    
    if not data:
        await callback.answer("⚠️ Ma'lumotlar yo'q.")
        return
    
    df = pd.DataFrame(data)
    # Keraksiz ustunlarni o'chirish yoki tartiblash (ixtiyoriy)
    cols = ['kod', 'ismlar', 'sinf', 'yonalish', 'majburiy', 'asosiy_1', 'asosiy_2', 'umumiy_ball', 'test_sanasi']
    df = df[[c for c in cols if c in df.columns]]
    
    path = f"students_{f_type}_{f_val}.xlsx".replace(" ", "_")
    df.to_excel(path, index=False)
    
    await callback.message.answer_document(FSInputFile(path), caption=caption)
    if os.path.exists(path):
        os.remove(path)
    await callback.answer()


@router.message(F.text == "📥 Excelga yuklash")
async def export_excel(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    data = get_all_students_for_excel()
    if not data:
        await message.answer("⚠️ Ma'lumotlar yo'q.")
        return
    
    df = pd.DataFrame(data)
    path = "students_results.xlsx"
    df.to_excel(path, index=False)
    
    await message.answer_document(FSInputFile(path), caption="📊 Barcha o'quvchilar natijalari")
    if os.path.exists(path):
        os.remove(path)


@router.message(F.text == "👨‍🏫 O'qituvchilarni boshqarish")
async def teachers_management(message: Message, state: FSMContext):
    await message.answer("👨‍🏫 <b>O'qituvchilarni boshqarish bo'limi:</b>", parse_mode="HTML", reply_markup=oqituvchi_boshqarish_keyboard())

@router.callback_query(F.data.startswith("oqituvchi_boshqar:"))
async def oqituvchi_boshqar_process(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]
    
    if action == "ro'yxat":
        oqituvchilar = oqituvchilar_hammasi()
        if not oqituvchilar:
            await callback.answer("⚠️ O'qituvchilar ro'yxati bo'sh.")
            return
        text = "📋 <b>O'qituvchilar ro'yxati:</b>\n\n"
        for o in oqituvchilar:
            text += f"👤 {o['ismlar']} | 🏫 {o['sinf']} | ID: <code>{o['user_id']}</code>\n"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=oqituvchi_boshqarish_keyboard())
    
    elif action == "qosh":
        await state.set_state(OqituvchiQosh.user_id_kutish)
        await callback.message.answer("🆔 O'qituvchining Telegram ID raqamini kiriting:")
        await callback.answer()
    
    elif action == "ochir":
        await callback.message.edit_text("❌ O'chirmoqchi bo'lgan o'qituvchini tanlang:", reply_markup=oqituvchi_ochirish_keyboard())
    
    elif action == "orqaga":
        await callback.message.delete()

@router.callback_query(F.data.startswith("oqituvchi_ochir:"))
async def oqituvchi_ochir_process(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[1])
    if oqituvchi_ochir(user_id):
        await callback.answer("✅ O'qituvchi o'chirildi")
    else:
        await callback.answer("❌ Xatolik yuz berdi")
    
    await callback.message.edit_text("❌ O'chirmoqchi bo'lgan o'qituvchini tanlang:", reply_markup=oqituvchi_ochirish_keyboard())

@router.message(OqituvchiQosh.user_id_kutish)
async def oqituvchi_id_get(message: Message, state: FSMContext):
    try:
        user_id = int(message.text)
        await state.update_data(teacher_id=user_id)
        await state.set_state(OqituvchiQosh.ismlar_kutish)
        await message.answer("👤 O'qituvchining ism-familiyasini kiriting:")
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")

@router.message(OqituvchiQosh.ismlar_kutish)
async def oqituvchi_ism_get(message: Message, state: FSMContext):
    await state.update_data(teacher_name=message.text)
    await state.set_state(OqituvchiQosh.sinf_kutish)
    await message.answer("🏫 O'qituvchi mas'ul bo'lgan sinfni kiriting (masalan: 11-A):", reply_markup=sinf_keyboard())

@router.callback_query(F.data.startswith("sinf:"), OqituvchiQosh.sinf_kutish)
async def oqituvchi_sinf_get(callback: CallbackQuery, state: FSMContext):
    sinf = callback.data.split(":")[1]
    data = await state.get_data()
    if oqituvchi_qosh(data['teacher_id'], data['teacher_name'], sinf):
        await callback.message.answer(f"✅ O'qituvchi {data['teacher_name']} ({sinf}) muvaffaqiyatli qo'shildi!")
    else:
        await callback.message.answer("❌ Xatolik yuz berdi.")
    await state.clear()
    await callback.answer()

# O'qituvchi uchun handlerlar
@router.message(F.text == "📊 Mening sinfim statistikasi")
async def teacher_stats(message: Message):
    teacher = oqituvchi_ol(message.from_user.id)
    if not teacher: return
    talabalar = talaba_filtrlangan(sinf=teacher['sinf'])
    if not talabalar:
        await message.answer("⚠️ Sinfingizda o'quvchilar yo'q.")
        return
    
    ballar = [t['umumiy_ball'] for t in talabalar if t['umumiy_ball'] is not None]
    avg = round(sum(ballar)/len(ballar), 2) if ballar else 0
    text = (
        f"🏫 <b>{teacher['sinf']} sinf statistikasi:</b>\n\n"
        f"👥 O'quvchilar soni: <b>{len(talabalar)} ta</b>\n"
        f"📈 O'rtacha ball: <b>{avg} ball</b>\n"
        f"🏆 Eng yuqori ball: <b>{max(ballar) if ballar else 0} ball</b>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "🏆 Mening sinfim reytingi")
async def teacher_ranking(message: Message):
    teacher = oqituvchi_ol(message.from_user.id)
    if not teacher: return
    talabalar = get_all_in_class(teacher['sinf'])
    if not talabalar:
        await message.answer("⚠️ Natijalar yo'q.")
        return
    text = f"🏆 <b>{teacher['sinf']} sinf reytingi:</b>\n\n"
    for i, t in enumerate(talabalar, 1):
        text += f"{i}. {t['ismlar']} — <b>{t['umumiy_ball']}</b>\n"
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "📋 Sinfim o'quvchilari")
async def teacher_students(message: Message):
    teacher = oqituvchi_ol(message.from_user.id)
    if not teacher: return
    talabalar = talaba_filtrlangan(sinf=teacher['sinf'])
    text = f"📋 <b>{teacher['sinf']} sinf o'quvchilari:</b>\n\n"
    for i, t in enumerate(talabalar, 1):
        text += f"{i}. {t['kod']} | {t['ismlar']}\n"
    await message.answer(text, parse_mode="HTML")

@router.message(F.text == "📥 Sinfim natijalari (Excel)")
async def teacher_excel(message: Message):
    teacher = oqituvchi_ol(message.from_user.id)
    if not teacher: return
    data = talaba_filtrlangan(sinf=teacher['sinf'])
    if not data:
        await message.answer("⚠️ Ma'lumotlar yo'q.")
        return
    df = pd.DataFrame(data)
    path = f"results_{teacher['sinf']}.xlsx"
    df.to_excel(path, index=False)
    await message.answer_document(FSInputFile(path), caption=f"📊 {teacher['sinf']} sinfi natijalari")
    if os.path.exists(path): os.remove(path)

@router.message(F.text == "🔍 Kod bo'yicha qidirish")
async def search_kod_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state) and not oqituvchi_ol(message.from_user.id): return
    await state.set_state(KodQidirish.kod_kutish)
    await message.answer("🔍 Qidirilayotgan o'quvchi <b>kodini</b> kiriting:", parse_mode="HTML")


@router.message(KodQidirish.kod_kutish)
async def search_kod_process(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer(f"❌ <b>{kod}</b> topilmadi.", parse_mode="HTML")
    else:
        from database import talaba_natijalari
        n = talaba_natijalari(kod, limit=1)
        ball = n[0]['umumiy_ball'] if n else 0
        text = (
            f"👤 <b>Ma'lumotlar:</b>\n"
            f"Kod: <b>{talaba['kod']}</b>\n"
            f"Ism: <b>{talaba['ismlar']}</b>\n"
            f"Sinf: <b>{talaba['sinf']}</b>\n"
            f"Yo'nalish: <b>{talaba['yonalish']}</b>\n"
            f"Oxirgi ball: <b>{ball}</b>"
        )
        await message.answer(text, parse_mode="HTML")
    await state.set_state(None)


@router.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await state.set_state(Broadcast.xabar_kutish)
    await message.answer("📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:")


@router.message(Broadcast.xabar_kutish)
async def broadcast_process(message: Message, state: FSMContext):
    user_ids = get_all_user_ids()
    count = 0
    for uid in user_ids:
        try:
            await message.copy_to(uid)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            continue
    await message.answer(f"✅ Xabar <b>{count}</b> ta foydalanuvchiga yuborildi.", parse_mode="HTML")
    await state.set_state(None)


@router.message(F.text == "🧹 Bazani tozalash")
async def clear_db_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await state.set_state(ConfirmDelete.tasdiqlash_kutish)
    await message.answer("⚠️ <b>DIQQAT!</b> Barcha o'quvchilar va natijalar o'chib ketadi. Tasdiqlaysizmi? (HA deb yozing)")


@router.message(ConfirmDelete.tasdiqlash_kutish)
async def clear_db_process(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    if message.text.strip().upper() == "HA":
        delete_all_data()
        await message.answer("✅ Barcha ma'lumotlar o'chirildi.", reply_markup=admin_menu_keyboard())
    else:
        await message.answer("❌ Bekor qilindi.", reply_markup=admin_menu_keyboard())
    await state.set_state(None)


@router.callback_query(F.data.startswith("murojaat_javob:"))
async def murojaat_javob_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split(":")[1]
    await state.update_data(reply_to=user_id)
    await state.set_state(MurojaatJavob.javob_kutish)
    await callback.message.answer(f"📝 Foydalanuvchiga (ID: {user_id}) javobingizni yozing:")
    await callback.answer()


@router.message(MurojaatJavob.javob_kutish)
async def murojaat_javob_send(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_to")
    try:
        await message.bot.send_message(
            user_id,
            f"📩 <b>Admin javobi:</b>\n\n{message.html_text}",
            parse_mode="HTML"
        )
        await message.answer("✅ Javob yuborildi.")
    except Exception as e:
        await message.answer(f"❌ Yuborishda xato: {e}")
    await state.set_state(None)
