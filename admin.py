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
    get_all_in_class,
    reminder_qosh, kutilayotgan_reminders_ol, reminder_holat_yangila, reminder_ochir,
    maktab_qosh, maktablar_ol, maktab_ochir, sinf_maktabga_bogla, maktab_sinflari_ol,
    guruh_qosh, guruhlar_ol, get_overall_ranking,
    appeals_ol, appeal_javob_ber, appeal_ol_id
)
from keyboards import (
    admin_menu_keyboard, yonalish_keyboard, tasdiqlash_keyboard, baza_tozalash_keyboard,
    yonalish_boshqarish_keyboard, yonalish_ochirish_keyboard,
    sinf_keyboard, sinf_boshqarish_keyboard, sinf_ochirish_keyboard,
    kalit_boshqarish_keyboard, kalit_actions_keyboard, kalit_yonalish_tanlash_keyboard,
    oquvchilar_filtrlash_keyboard, sinf_tanlash_keyboard, yonalish_tanlash_keyboard, filter_actions_keyboard,
    settings_keyboard, request_actions_keyboard, ranking_keyboard, sinf_tanlash_ranking_keyboard,
    oqituvchi_boshqarish_keyboard, oqituvchi_menu_keyboard, oqituvchi_ochirish_keyboard,
    reminder_boshqarish_keyboard, maktab_boshqarish_keyboard, guruh_boshqarish_keyboard,
    reminder_list_keyboard, maktab_list_keyboard, maktab_detail_keyboard,
    appeals_keyboard, appeal_action_keyboard
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

class OqituvchiQosh(StatesGroup):
    user_id_kutish = State()
    ismlar_kutish = State()
    sinf_kutish = State()

class NatijaTahrirlash(StatesGroup):
    kod_kutish = State()
    majburiy_kutish = State()
    asosiy1_kutish = State()
    asosiy2_kutish = State()

class ReminderAdd(StatesGroup):
    xabar_kutish = State()
    vaqt_kutish = State()

class MaktabAdd(StatesGroup):
    nomi_kutish = State()

class MaktabSinfAdd(StatesGroup):
    maktab_id = State()
    sinf_nomi = State()

class AppealReply(StatesGroup):
    appeal_id = State()
    javob_kutish = State()

# ─────────────────────────────────────────
# Yordamchi funksiyalar
# ─────────────────────────────────────────

async def is_admin(message: Message, state: FSMContext):
    data = await state.get_data()
    return data.get("admin") is True

async def admin_tekshir(state: FSMContext, user_id: int = None) -> bool:
    data = await state.get_data()
    if data.get("admin") is True:
        return True
    if user_id and is_admin_id(user_id):
        await state.update_data(admin=True)
        return True
    return False

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

async def guruhlarga_yangi_oquvchi_yuborish(bot: Bot, talaba: dict, natija: dict = None):
    """Guruhlarga yangi qo'shilgan o'quvchi ma'lumotlarini yuboradi."""
    from database import guruhlar_ol
    guruhlar = guruhlar_ol()
    if not guruhlar: return

    text = (
        f"🆕 <b>Yangi o'quvchi qo'shildi!</b>\n\n"
        f"👤 Ism: <b>{talaba['ismlar']}</b>\n"
        f"🆔 Kod: <b>{talaba['kod']}</b>\n"
        f"🏫 Sinf: <b>{talaba['sinf']}</b>\n"
        f"🎯 Yo'nalish: <b>{talaba['yonalish']}</b>"
    )
    if natija:
        text += f"\n📊 Birinchi natija: <b>{natija['umumiy_ball']} ball</b>"

    for g in guruhlar:
        try:
            await bot.send_message(g['chat_id'], text, parse_mode="HTML")
        except Exception:
            pass

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
            diff_text = f"\n📉 Natijangiz <b>{diff} ballga</b> o'zgardi. Keyingi safar yanada yaxshoreq bo'ladi! 💪"
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
    if await admin_tekshir(state, message.from_user.id):
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
    if not await admin_tekshir(state, message.from_user.id): return
    await message.answer("Yo'nalishlarni boshqarish menyusi:", reply_markup=yonalish_boshqarish_keyboard())


@router.callback_query(F.data.startswith("yonalish_boshqar:"))
async def yonalish_boshqar_actions(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
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
    await callback.answer()


@router.message(YonalishBoshqar.nomi_kutish)
async def yonalish_nomi_saqla(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    nomi = message.text.strip()
    if yonalish_qosh(nomi):
        await message.answer(f"✅ Yangi yo'nalish qo'shildi: <b>{nomi}</b>",
                             parse_mode="HTML", reply_markup=admin_menu_keyboard())
    else:
        await message.answer("❌ Bu yo'nalish allaqachon mavjud.")
    await state.set_state(None)


@router.callback_query(F.data.startswith("yonalish_ochir:"))
async def yonalish_ochir_tasdiq(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
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
    if not await admin_tekshir(state, message.from_user.id): return
    await message.answer("Sinflarni boshqarish menyusi:", reply_markup=sinf_boshqarish_keyboard())


@router.callback_query(F.data.startswith("sinf_boshqar:"))
async def sinf_boshqar_actions(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
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
    await callback.answer()


@router.message(SinfBoshqar.nomi_kutish)
async def sinf_nomi_saqla(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    nomi = message.text.strip()
    if sinf_qosh(nomi):
        await message.answer(f"✅ Yangi sinf qo'shildi: <b>{nomi}</b>",
                             parse_mode="HTML", reply_markup=admin_menu_keyboard())
    else:
        await message.answer("❌ Bu sinf allaqachon mavjud.")
    await state.set_state(None)


@router.callback_query(F.data.startswith("sinf_ochir:"))
async def sinf_ochir_tasdiq(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
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
    if not await admin_tekshir(state, message.from_user.id): return
    await message.answer("Test kalitlarini boshqarish menyusi:", reply_markup=kalit_boshqarish_keyboard())


@router.callback_query(F.data.startswith("kalit_boshqar:"))
async def kalit_boshqar_actions(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    action = callback.data.split(":")[1]

    if action == "ro'yxat":
        kalitlar = kalit_ol()
        if not kalitlar:
            await callback.message.edit_text("⚠️ Hozircha testlar yo'q.", reply_markup=kalit_boshqarish_keyboard())
        else:
            await callback.message.edit_text("📋 Testni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"{'🔓' if k['holat']=='ochiq' else '🔒'} {k['test_nomi']}", callback_data=f"kalit_detail:{k['test_nomi']}")] for k in kalitlar
            ] + [[InlineKeyboardButton(text="🔙 Orqaga", callback_data="kalit_boshqar:orqaga")]]))

    elif action == "qosh":
        await state.set_state(KalitBoshqar.nomi_kutish)
        await callback.message.edit_text("📝 Yangi test nomini kiriting:")

    elif action == "yonalish_qosh":
        await callback.message.edit_text("🎯 Qaysi yo'nalish uchun kalit qo'shmoqchisiz?", reply_markup=kalit_yonalish_tanlash_keyboard())

    elif action == "ochir":
        kalitlar = kalit_ol()
        await callback.message.edit_text("❌ O'chirmoqchi bo'lgan testni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"❌ {k['test_nomi']}", callback_data=f"kalit_del:{k['test_nomi']}")] for k in kalitlar
        ] + [[InlineKeyboardButton(text="🔙 Orqaga", callback_data="kalit_boshqar:orqaga")]]))

    elif action == "orqaga":
        await state.set_state(None)
        await callback.message.edit_text("Test kalitlarini boshqarish menyusi:", reply_markup=kalit_boshqarish_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("kalit_detail:"))
async def kalit_detail(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    test_nomi = callback.data.split(":")[1]
    kalitlar = kalit_ol()
    k = next((x for x in kalitlar if x['test_nomi'] == test_nomi), None)
    if not k: return
    
    text = (
        f"📋 <b>Test:</b> {k['test_nomi']}\n"
        f"🎯 <b>Yo'nalish:</b> {k.get('yonalish') or 'Umumiy'}\n"
        f"🔑 <b>Kalitlar:</b> <code>{k['kalitlar']}</code>\n"
        f"📊 <b>Holat:</b> {'Ochiq' if k['holat']=='ochiq' else 'Yopiq'}"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kalit_actions_keyboard(k['test_nomi'], k['holat']))
    await callback.answer()

@router.callback_query(F.data.startswith("kalit_status:"))
async def kalit_status_change(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    test_nomi = callback.data.split(":")[1]
    kalit_holat_ozgartir(test_nomi)
    await kalit_detail(callback, state)

@router.callback_query(F.data.startswith("kalit_del:"))
async def kalit_delete(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    test_nomi = callback.data.split(":")[1]
    kalit_ochir(test_nomi)
    await callback.answer(f"✅ {test_nomi} o'chirildi")
    await kalit_boshqar_actions(callback, state)

@router.message(KalitBoshqar.nomi_kutish)
async def kalit_nomi_save(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await state.update_data(test_nomi=message.text.strip())
    await state.set_state(KalitBoshqar.kalit_kutish)
    await message.answer("🔑 Kalitlarni kiriting (masalan: abcd...):")

@router.message(KalitBoshqar.kalit_kutish)
async def kalit_save(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    data = await state.get_data()
    kalitlar = message.text.strip().lower()
    kalit_qosh(data['test_nomi'], kalitlar)
    await message.answer(f"✅ Test qo'shildi: <b>{data['test_nomi']}</b>", parse_mode="HTML", reply_markup=admin_menu_keyboard())
    await state.set_state(None)

@router.callback_query(F.data.startswith("kalit_yonalish:"))
async def kalit_yonalish_selected(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    yonalish = callback.data.split(":")[1]
    await state.update_data(yonalish_nomi=yonalish)
    await state.set_state(KalitBoshqar.yonalish_nomi_kutish)
    await callback.message.edit_text(f"🎯 Yo'nalish: {yonalish}\n📝 Test nomini kiriting:")
    await callback.answer()

@router.message(KalitBoshqar.yonalish_nomi_kutish)
async def kalit_yonalish_nomi_save(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await state.update_data(test_nomi=message.text.strip())
    await state.set_state(KalitBoshqar.yonalish_kalit_kutish)
    await message.answer("🔑 Kalitlarni kiriting:")

@router.message(KalitBoshqar.yonalish_kalit_kutish)
async def kalit_yonalish_save(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    data = await state.get_data()
    kalit_qosh(data['test_nomi'], message.text.strip().lower(), data['yonalish_nomi'])
    await message.answer(f"✅ Yo'nalishli test qo'shildi: <b>{data['test_nomi']}</b>", parse_mode="HTML", reply_markup=admin_menu_keyboard())
    await state.set_state(None)

# ─────────────────────────────────────────
# O'quvchi QO'SHISH (Bildirishnoma bilan)
# ─────────────────────────────────────────

@router.message(F.text == "➕ O'quvchi qo'shish")
async def talaba_qosh_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await state.set_state(TalabaQosh.kod_kutish)
    await message.answer("📝 O'quvchining shaxsiy <b>kodini</b> kiriting:", parse_mode="HTML")


@router.message(TalabaQosh.kod_kutish)
async def talaba_kod(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    kod = message.text.strip().upper()
    await state.update_data(kod=kod)
    await state.set_state(TalabaQosh.yonalish_kutish)
    await message.answer(f"✅ Kod: <b>{kod}</b>\n\nYo'nalishni tanlang:",
                         reply_markup=yonalish_keyboard(), parse_mode="HTML")
@router.callback_query(TalabaQosh.yonalish_kutish, F.data.startswith("yonalish:"))
async def talaba_yonalish(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    yonalish = callback.data.split(":", 1)[1]
    await state.update_data(yonalish=yonalish)
    await state.set_state(TalabaQosh.sinf_kutish)
    await callback.message.edit_text(f"🎯 Yo'nalish: <b>{yonalish}</b>\n\nSinfni tanlang:",
                                     reply_markup=sinf_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(TalabaQosh.sinf_kutish, F.data.startswith("sinf:"))
async def talaba_sinf(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    sinf = callback.data.split(":", 1)[1]
    await state.update_data(sinf=sinf)
    await state.set_state(TalabaQosh.ismlar_kutish)
    await callback.message.edit_text(f"🏫 Sinf: <b>{sinf}</b>\n\n👤 O'quvchining ism-familiyasini kiriting:",
                                     parse_mode="HTML")
    await callback.answer()


@router.message(TalabaQosh.ismlar_kutish)
async def talaba_ismlar(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    ismlar = message.text.strip()
    await state.update_data(ismlar=ismlar)
    await state.set_state(TalabaQosh.majburiy_kutish)
    await message.answer(f"👤 Ism: <b>{ismlar}</b>\n\n📘 <b>Majburiy fanlar</b> bo'yicha to'g'ri javoblar sonini kiriting (0-30):",
                         parse_mode="HTML")


@router.message(TalabaQosh.majburiy_kutish)
async def talaba_majburiy(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer("❌ Noto'g'ri son. 0 dan 30 gacha raqam kiriting:")
        return
    await state.update_data(majburiy=son)
    await state.set_state(TalabaQosh.asosiy1_kutish)
    await message.answer("📗 <b>1-asosiy fan</b> bo'yicha to'g'ri javoblar sonini kiriting (0-30):",
                         parse_mode="HTML")


@router.message(TalabaQosh.asosiy1_kutish)
async def talaba_asosiy1(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer("❌ Noto'g'ri son. 0 dan 30 gacha raqam kiriting:")
        return
    await state.update_data(asosiy1=son)
    await state.set_state(TalabaQosh.asosiy2_kutish)
    await message.answer("📙 <b>2-asosiy fan</b> bo'yicha to'g'ri javoblar sonini kiriting (0-30):",
                         parse_mode="HTML")


@router.message(TalabaQosh.asosiy2_kutish)
async def talaba_asosiy2(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer("❌ Noto'g'ri son. 0 dan 30 gacha raqam kiriting:")
        return
    await state.update_data(asosiy2=son)
    data = await state.get_data()
    
    ball = ball_hisobla(data['majburiy'], data['asosiy1'], data['asosiy2'])
    await state.update_data(umumiy_ball=ball)
    
    text = (
        f"🧐 <b>Ma'lumotlarni tekshiring:</b>\n\n"
        f"🆔 Kod: <b>{data['kod']}</b>\n"
        f"👤 Ism: <b>{data['ismlar']}</b>\n"
        f"🏫 Sinf: <b>{data['sinf']}</b>\n"
        f"🎯 Yo'nalish: <b>{data['yonalish']}</b>\n\n"
        f"📊 <b>Natijalar:</b>\n"
        f"  📘 Majburiy: {data['majburiy']}/30\n"
        f"  📗 1-asosiy: {data['asosiy1']}/30\n"
        f"  📙 2-asosiy: {data['asosiy2']}/30\n"
        f"━━━━━━━━━━━━━━\n"
        f"🏆 <b>Umumiy ball: {ball}</b>"
    )
    await state.set_state(TalabaQosh.tasdiq_kutish)
    await message.answer(text, parse_mode="HTML", reply_markup=tasdiqlash_keyboard())


@router.callback_query(TalabaQosh.tasdiq_kutish, F.data.startswith("tasdiq:"))
async def talaba_tasdiq(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    action = callback.data.split(":")[1]
    
    if action == "ha":
        data = await state.get_data()
        talaba = {
            'kod': data['kod'],
            'ismlar': data['ismlar'],
            'yonalish': data['yonalish'],
            'sinf': data['sinf']
        }
        natija = {
            'majburiy': data['majburiy'],
            'asosiy_1': data['asosiy1'],
            'asosiy_2': data['asosiy2'],
            'umumiy_ball': data['umumiy_ball']
        }
        
        talaba_qosh(talaba['kod'], talaba['ismlar'], talaba['yonalish'], talaba['sinf'])
        natija_qosh(talaba['kod'], natija['majburiy'], natija['asosiy_1'], natija['asosiy_2'], natija['umumiy_ball'])
        
        await callback.message.edit_text("✅ Ma'lumotlar muvaffaqiyatli saqlandi!", reply_markup=None)
        await callback.message.answer("Asosiy menyu:", reply_markup=admin_menu_keyboard())
        
        # Bildirishnomalar
        asyncio.create_task(bildirishnoma_yuborish(callback.bot, talaba['kod'], natija, talaba))
        asyncio.create_task(guruhlarga_yangi_oquvchi_yuborish(callback.bot, talaba, natija))
        
    else:
        await callback.message.edit_text("❌ Bekor qilindi.", reply_markup=None)
        await callback.message.answer("Asosiy menyu:", reply_markup=admin_menu_keyboard())
    
    await state.set_state(None)
    await callback.answer()

# ─────────────────────────────────────────
# Natijani Tahrirlash
# ─────────────────────────────────────────

@router.message(F.text == "✏️ Natijani tahrirlash")
async def natija_tahrirlash_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await state.set_state(NatijaTahrirlash.kod_kutish)
    await message.answer("🔍 Tahrirlash uchun o'quvchi <b>kodini</b> kiriting:", parse_mode="HTML")


@router.message(NatijaTahrirlash.kod_kutish)
async def natija_tahrir_kod(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer("❌ Bunday kodli o'quvchi topilmadi.")
        await state.set_state(None)
        return
    
    await state.update_data(kod=kod)
    await state.set_state(NatijaTahrirlash.majburiy_kutish)
    await message.answer(f"👤 O'quvchi: <b>{talaba['ismlar']}</b>\n\n📘 Yangi <b>majburiy</b> ballni kiriting (0-30):", parse_mode="HTML")


@router.message(NatijaTahrirlash.majburiy_kutish)
async def natija_tahrir_majburiy(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer("❌ Noto'g'ri son.")
        return
    await state.update_data(majburiy=son)
    await state.set_state(NatijaTahrirlash.asosiy1_kutish)
    await message.answer("📗 Yangi <b>1-asosiy</b> ballni kiriting (0-30):", parse_mode="HTML")


@router.message(NatijaTahrirlash.asosiy1_kutish)
async def natija_tahrir_asosiy1(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer("❌ Noto'g'ri son.")
        return
    await state.update_data(asosiy1=son)
    await state.set_state(NatijaTahrirlash.asosiy2_kutish)
    await message.answer("📙 Yangi <b>2-asosiy</b> ballni kiriting (0-30):", parse_mode="HTML")


@router.message(NatijaTahrirlash.asosiy2_kutish)
async def natija_tahrir_asosiy2(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    son = _son_tekshir(message.text)
    if son is None:
        await message.answer("❌ Noto'g'ri son.")
        return
    data = await state.get_data()
    ball = ball_hisobla(data['majburiy'], data['asosiy1'], son)
    
    # Ma'lumotlarni yangilash
    natija_qosh(data['kod'], data['majburiy'], data['asosiy1'], son, ball)
    
    await message.answer(f"✅ Natija yangilandi! Yangi ball: <b>{ball}</b>", parse_mode="HTML", reply_markup=admin_menu_keyboard())
    await state.set_state(None)

# ─────────────────────────────────────────
# Exceldan IMPORT (Bildirishnoma bilan)
# ─────────────────────────────────────────

@router.message(F.text == "📥 Exceldan import")
async def excel_import_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await state.set_state(ExcelImport.fayl_kutish)
    await message.answer(
        "📥 <b>Excel faylini yuboring.</b>\n\n"
        "Fayl ustunlari tartibi:\n"
        "1. Kod\n"
        "2. Ism-familiya\n"
        "3. Yo'nalish\n"
        "4. Sinf\n"
        "5. Majburiy (to'g'ri javoblar soni)\n"
        "6. 1-asosiy\n"
        "7. 2-asosiy",
        parse_mode="HTML"
    )


@router.message(ExcelImport.fayl_kutish, F.document)
async def excel_import_process(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    file_id = message.document.file_id
    file = await message.bot.get_file(file_id)
    file_path = file.file_path
    
    download_path = f"import_{message.from_user.id}.xlsx"
    await message.bot.download_file(file_path, download_path)
    
    try:
        df = pd.read_excel(download_path)
        count = 0
        for _, row in df.iterrows():
            try:
                kod = str(row.iloc[0]).strip().upper()
                ismlar = str(row.iloc[1]).strip()
                yonalish = str(row.iloc[2]).strip()
                sinf = str(row.iloc[3]).strip()
                majburiy = int(row.iloc[4])
                asosiy1 = int(row.iloc[5])
                asosiy2 = int(row.iloc[6])
                
                ball = ball_hisobla(majburiy, asosiy1, asosiy2)
                
                talaba_qosh(kod, ismlar, yonalish, sinf)
                natija_qosh(kod, majburiy, asosiy1, asosiy2, ball)
                
                # Bildirishnomalarni fonda yuboramiz
                talaba = {'kod': kod, 'ismlar': ismlar, 'yonalish': yonalish, 'sinf': sinf}
                natija = {'majburiy': majburiy, 'asosiy_1': asosiy1, 'asosiy_2': asosiy2, 'umumiy_ball': ball}
                asyncio.create_task(bildirishnoma_yuborish(message.bot, kod, natija, talaba))
                
                count += 1
            except Exception:
                continue
        
        await message.answer(f"✅ <b>{count}</b> ta o'quvchi ma'lumotlari muvaffaqiyatli import qilindi!", parse_mode="HTML", reply_markup=admin_menu_keyboard())
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    
    if os.path.exists(download_path):
        os.remove(download_path)
    await state.set_state(None)

# ─────────────────────────────────────────
# Statistika va Sozlamalar
# ─────────────────────────────────────────

@router.message(F.text == "📊 Statistika")
async def stats_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    res = statistika()
    if not res:
        await message.answer("⚠️ Ma'lumotlar yo'q.")
        return
    
    text = (
        f"📊 <b>Umumiy statistika:</b>\n\n"
        f"👥 Jami o'quvchilar: <b>{res['jami']} ta</b>\n"
        f"📈 O'rtacha ball: <b>{res['ortacha']} ball</b>\n"
        f"🏆 Eng yuqori ball: <b>{res['max_ball']} ball</b>\n"
        f"📉 Eng past ball: <b>{res['min_ball']} ball</b>"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "⚙️ Sozlamalar")
async def settings_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    ranking_enabled = get_setting('ranking_enabled', 'True')
    stats_enabled = get_setting('stats_enabled', 'True')
    
    text = (
        "⚙️ <b>Bot sozlamalari:</b>\n\n"
        f"🏆 Reyting (Top-50): <b>{'✅ Yoqilgan' if ranking_enabled == 'True' else '❌ O' + chr(39) + 'chirilgan'}</b>\n"
        f"📈 Statistika: <b>{'✅ Yoqilgan' if stats_enabled == 'True' else '❌ O' + chr(39) + 'chirilgan'}</b>\n\n"
        "O'zgartirish uchun tugmalarni bosing:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=settings_keyboard(ranking_enabled, stats_enabled))


@router.callback_query(F.data.startswith("toggle_setting:"))
async def toggle_setting_handler(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    key = callback.data.split(":")[1]
    current = get_setting(key, 'True')
    new_value = 'False' if current == 'True' else 'True'
    set_setting(key, new_value)
    
    ranking_enabled = get_setting('ranking_enabled', 'True')
    stats_enabled = get_setting('stats_enabled', 'True')
    
    text = (
        "⚙️ <b>Bot sozlamalari:</b>\n\n"
        f"🏆 Reyting (Top-50): <b>{'✅ Yoqilgan' if ranking_enabled == 'True' else '❌ O' + chr(39) + 'chirilgan'}</b>\n"
        f"📈 Statistika: <b>{'✅ Yoqilgan' if stats_enabled == 'True' else '❌ O' + chr(39) + 'chirilgan'}</b>\n\n"
        "O'zgartirish uchun tugmalarni bosing:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=settings_keyboard(ranking_enabled, stats_enabled))
    await callback.answer("✅ Sozlama yangilandi")


@router.message(F.text == "🔔 So'rovlar")
async def requests_list(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    requests = get_pending_requests()
    if not requests:
        await message.answer("✅ Hozircha yangi so'rovlar yo'q.")
        return
    
    for req in requests:
        text = (
            f"🔔 <b>Yangi kirish so'rovi:</b>\n\n"
            f"👤 Ism: <b>{req['ismlar']}</b>\n"
            f"🏫 Sinf: <b>{req['sinf']}</b>\n"
            f"🎯 Yo'nalish: <b>{req.get('yonalish', 'Noma' + chr(39) + 'lum')}</b>\n"
            f"🆔 Kod: <code>{req['talaba_kod']}</code>\n"
            f"👤 Telegram ID: <code>{req['user_id']}</code>"
        )
        await message.answer(text, parse_mode="HTML", reply_markup=request_actions_keyboard(req['id'], req['user_id']))


@router.callback_query(F.data.startswith("request_action:"))
async def request_action_handler(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    data_parts = callback.data.split(":")
    action = data_parts[1]
    target_id = int(data_parts[2]) # request_id yoki user_id bo'lishi mumkin
    
    from database import get_connection, release_connection, revoke_access_by_user
    from datetime import datetime, timedelta

    if action == "revoke":
        revoke_access_by_user(target_id)
        await callback.answer("🚫 Ruxsat qaytarib olindi")
        await callback.message.edit_text(f"🚫 Foydalanuvchining (ID: {target_id}) barcha ruxsatlari bekor qilindi.")
        return

    request_id = target_id
    if action == "approve":
        update_request_status(request_id, 'tasdiqlandi')
        # User_id ni topish
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM access_requests WHERE id = %s", (request_id,))
        user_id = cur.fetchone()[0]
        cur.close()
        release_connection(conn)
        
        try:
            await callback.bot.send_message(user_id, "✅ Sizning botdan foydalanish so'rovingiz admin tomonidan tasdiqlandi! Endi natijalaringizni ko'rishingiz mumkin.")
        except Exception: pass
        await callback.message.edit_text("✅ So'rov tasdiqlandi.")
        
    elif action == "reject":
        update_request_status(request_id, 'rad_etildi')
        await callback.message.edit_text("❌ So'rov rad etildi.")
    
    await callback.answer()
# ─────────────────────────────────────────
# O'quvchilar ro'yxati va Excelga yuklash
# ─────────────────────────────────────────

@router.message(F.text == "📋 O'quvchilar ro'yxati")
async def students_list(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await message.answer("📋 O'quvchilar ro'yxatini ko'rish usulini tanlang:", reply_markup=oquvchilar_filtrlash_keyboard())


@router.callback_query(F.data.startswith("filter_type:"))
async def filter_type_process(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    ftype = callback.data.split(":")[1]
    if ftype == "all":
        talabalar = talaba_hammasi()
        if not talabalar:
            await callback.answer("⚠️ O'quvchilar yo'q.", show_alert=True)
            return
        text = f"📋 <b>Barcha o'quvchilar ({len(talabalar)} ta):</b>\n\n"
        for t in talabalar[:50]: # Dastlabki 50 tasi
            text += f"🔹 {t['kod']} | {t['ismlar']} | {t['sinf']}\n"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=filter_actions_keyboard())
    elif ftype == "sinf":
        await callback.message.edit_text("🏫 Sinfni tanlang:", reply_markup=sinf_tanlash_keyboard())
    elif ftype == "yonalish":
        await callback.message.edit_text("🎯 Yo'nalishni tanlang:", reply_markup=yonalish_tanlash_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("filter_val:"))
async def filter_val_process(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    parts = callback.data.split(":")
    ftype = parts[1]
    fval = parts[2]
    
    if ftype == "sinf":
        talabalar = talaba_filtrlangan(sinf=fval)
    else:
        talabalar = talaba_filtrlangan(yonalish=fval)
        
    if not talabalar:
        await callback.answer("⚠️ Bu filtr bo'yicha o'quvchilar topilmadi.", show_alert=True)
        return
        
    text = f"📋 <b>Filtrlangan ro'yxat ({len(talabalar)} ta):</b>\n\n"
    for t in talabalar[:50]:
        text += f"🔹 {t['kod']} | {t['ismlar']} | {t['sinf']}\n"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=filter_actions_keyboard())
    await callback.answer()


@router.message(F.text == "📥 Excelga yuklash")
async def export_excel(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    data = get_all_students_for_excel()
    if not data:
        await message.answer("⚠️ Ma'lumotlar yo'q.")
        return
    
    path = f"oquvchilar_{message.from_user.id}.xlsx"
    df = pd.DataFrame(data)
    df.to_excel(path, index=False)
    
    await message.answer_document(FSInputFile(path), caption="📊 Barcha o'quvchilar va natijalar ro'yxati (Excel)")
    if os.path.exists(path):
        os.remove(path)

# ─────────────────────────────────────────
# O'qituvchilarni boshqarish
# ─────────────────────────────────────────

@router.message(F.text == "👨‍🏫 O'qituvchilarni boshqarish")
async def oqituvchi_menu(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await message.answer("👨‍🏫 O'qituvchilarni boshqarish bo'limi:", reply_markup=oqituvchi_boshqarish_keyboard())


@router.callback_query(F.data.startswith("oqituvchi_boshqar:"))
async def oqituvchi_boshqar_actions(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    action = callback.data.split(":")[1]
    
    if action == "ro'yxat":
        oqituvchilar = oqituvchilar_hammasi()
        if not oqituvchilar:
            await callback.answer("⚠️ O'qituvchilar hali qo'shilmagan.", show_alert=True)
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
    await callback.answer()


@router.callback_query(F.data.startswith("oqituvchi_ochir:"))
async def oqituvchi_ochir_process(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    user_id = int(callback.data.split(":")[1])
    if oqituvchi_ochir(user_id):
        await callback.answer("✅ O'qituvchi o'chirildi")
    else:
        await callback.answer("❌ Xatolik yuz berdi")
    await callback.message.edit_text("❌ O'chirmoqchi bo'lgan o'qituvchini tanlang:", reply_markup=oqituvchi_ochirish_keyboard())


@router.message(OqituvchiQosh.user_id_kutish)
async def oqituvchi_id_get(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    try:
        user_id = int(message.text)
        await state.update_data(teacher_id=user_id)
        await state.set_state(OqituvchiQosh.ismlar_kutish)
        await message.answer("👤 O'qituvchining ism-familiyasini kiriting:")
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting!")


@router.message(OqituvchiQosh.ismlar_kutish)
async def oqituvchi_ism_get(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await state.update_data(teacher_name=message.text)
    await state.set_state(OqituvchiQosh.sinf_kutish)
    await message.answer("🏫 O'qituvchi mas'ul bo'lgan sinfni kiriting (masalan: 11-A):", reply_markup=sinf_keyboard())


@router.callback_query(F.data.startswith("sinf:"), OqituvchiQosh.sinf_kutish)
async def oqituvchi_sinf_get(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    sinf = callback.data.split(":")[1]
    data = await state.get_data()
    if oqituvchi_qosh(data['teacher_id'], data['teacher_name'], sinf):
        await callback.message.answer(f"✅ O'qituvchi {data['teacher_name']} ({sinf}) muvaffaqiyatli qo'shildi!")
    else:
        await callback.message.answer("❌ Xatolik yuz berdi.")
    await state.clear()
    await state.update_data(admin=True)
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
    path = f"sinf_{teacher['sinf']}.xlsx"
    pd.DataFrame(data).to_excel(path, index=False)
    await message.answer_document(FSInputFile(path), caption=f"📊 {teacher['sinf']} sinf natijalari")
    if os.path.exists(path): os.remove(path)

# ─────────────────────────────────────────
# Reyting va Xabar yuborish
# ─────────────────────────────────────────

@router.message(F.text == "🏆 Reyting")
async def ranking_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await message.answer("🏆 Reyting bo'limi:", reply_markup=ranking_keyboard(is_admin=True))


@router.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await state.set_state(Broadcast.xabar_kutish)
    await message.answer("📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:")


@router.message(Broadcast.xabar_kutish)
async def broadcast_process(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
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


@router.message(F.text == "⚖️ Apellyatsiyalar")
async def appeals_list_view(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    appeals = appeals_ol('kutilmoqda')
    if not appeals:
        await message.answer("✅ Hozircha yangi apellyatsiyalar yo'q.")
        return
    await message.answer("⚖️ <b>Yangi apellyatsiyalar:</b>", parse_mode="HTML", reply_markup=appeals_keyboard(appeals))

# ─────────────────────────────────────────
# Bazani tozalash (MUAMMO TUZATILGAN JOY)
# ─────────────────────────────────────────

@router.message(F.text == "🧹 Bazani tozalash")
async def clear_db_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await message.answer(
        "⚠️ <b>DIQQAT!</b> Barcha o'quvchilar va natijalar o'chib ketadi. Tasdiqlaysizmi?",
        reply_markup=baza_tozalash_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("baza_tozalash:"))
async def clear_db_callback(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id):
        await callback.answer("Siz admin emassiz!", show_alert=True)
        return
    
    action = callback.data.split(":")[1]
    
    if action == "ha":
        delete_all_data()
        try:
            await callback.message.edit_text("✅ Barcha ma'lumotlar o'chirildi.")
        except Exception:
            await callback.message.answer("✅ Barcha ma'lumotlar o'chirildi.")
        await callback.message.answer("Asosiy menyu:", reply_markup=admin_menu_keyboard())
    else:
        try:
            await callback.message.edit_text("❌ Bekor qilindi.")
        except Exception:
            await callback.message.answer("❌ Bekor qilindi.")
        await callback.message.answer("Asosiy menyu:", reply_markup=admin_menu_keyboard())
    
    await callback.answer()
    await state.set_state(None)

# ─────────────────────────────────────────
# Boshqa callback handlerlar
# ─────────────────────────────────────────

@router.callback_query(F.data.startswith("murojaat_javob:"))
async def murojaat_javob_start(callback: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, callback.from_user.id): return
    user_id = callback.data.split(":")[1]
    await state.update_data(reply_to=user_id)
    await state.set_state(MurojaatJavob.javob_kutish)
    await callback.message.answer(f"📝 Foydalanuvchiga (ID: {user_id}) javobingizni yozing:")
    await callback.answer()


@router.message(MurojaatJavob.javob_kutish)
async def murojaat_javob_send(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
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

# ─────────────────────────────────────────
# Eslatma tizimi handlerlari
# ─────────────────────────────────────────

@router.message(F.text == "⏰ Eslatmalar")
async def reminder_menu(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await message.answer("⏰ Eslatma tizimi bo'limi:", reply_markup=reminder_boshqarish_keyboard())


@router.callback_query(F.data == "reminder:qosh")
async def reminder_qosh_start(call: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, call.from_user.id): return
    await state.set_state(ReminderAdd.xabar_kutish)
    await call.message.edit_text("📝 Eslatma xabarini kiriting:")
    await call.answer()


@router.callback_query(F.data == "reminder:ro'yxat")
async def reminder_list_view(call: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, call.from_user.id): return
    reminders = kutilayotgan_reminders_ol()
    if not reminders:
        await call.answer("📋 Kutilayotgan eslatmalar yo'q.", show_alert=True)
        return
    await call.message.edit_text("📋 <b>Kutilayotgan eslatmalar:</b>\n\nO'chirish uchun ustiga bosing:", parse_mode="HTML", reply_markup=reminder_list_keyboard(reminders))
    await call.answer()


@router.callback_query(F.data.startswith("reminder_del:"))
async def reminder_delete_process(call: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, call.from_user.id): return
    rid = int(call.data.split(":")[1])
    reminder_ochir(rid)
    await call.answer("✅ Eslatma o'chirildi")
    reminders = kutilayotgan_reminders_ol()
    if reminders:
        await call.message.edit_reply_markup(reply_markup=reminder_list_keyboard(reminders))
    else:
        await call.message.edit_text("⏰ Eslatma tizimi bo'limi:", reply_markup=reminder_boshqarish_keyboard())


@router.callback_query(F.data == "reminder:orqaga")
async def reminder_back(call: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, call.from_user.id): return
    await call.message.edit_text("⏰ Eslatma tizimi bo'limi:", reply_markup=reminder_boshqarish_keyboard())
    await call.answer()


@router.message(ReminderAdd.xabar_kutish)
async def reminder_xabar_save(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await state.update_data(reminder_xabar=message.text)
    await state.set_state(ReminderAdd.vaqt_kutish)
    await message.answer("📅 Yuborish vaqtini kiriting (YYYY-MM-DD HH:MM formatida):\nMasalan: 2024-05-20 09:00")


@router.message(ReminderAdd.vaqt_kutish)
async def reminder_vaqt_save(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    try:
        from datetime import datetime
        datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        data = await state.get_data()
        reminder_qosh(data['reminder_xabar'], message.text)
        await state.clear()
        await state.update_data(admin=True)
        await message.answer("✅ Eslatma muvaffaqiyatli saqlandi!", reply_markup=admin_menu_keyboard())
    except ValueError:
        await message.answer("❌ Vaqt formati noto'g'ri. Qaytadan kiriting (YYYY-MM-DD HH:MM):")

# ─────────────────────────────────────────
# Maktab va Guruh boshqaruvi
# ─────────────────────────────────────────

@router.message(F.text == "🏫 Maktablarni boshqarish")
async def maktab_menu(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await message.answer("🏫 Maktablarni boshqarish bo'limi:", reply_markup=maktab_boshqarish_keyboard())


@router.callback_query(F.data == "maktab:qosh")
async def maktab_qosh_start(call: CallbackQuery, state: FSMContext):
    if not await admin_tekshir(state, call.from_user.id): return
    await state.set_state(MaktabAdd.nomi_kutish)
    await call.message.edit_text("🏫 Yangi maktab nomini kiriting:")
    await call.answer()


@router.message(MaktabAdd.nomi_kutish)
async def maktab_nomi_save(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    nomi = message.text.strip()
    from database import maktab_qosh
    if maktab_qosh(nomi):
        await message.answer(f"✅ Maktab qo'shildi: {nomi}", reply_markup=admin_menu_keyboard())
    else:
        await message.answer("❌ Xato yuz berdi.")
    await state.clear()
    await state.update_data(admin=True)


@router.message(F.text == "📢 Guruhlarni boshqarish")
async def guruh_menu(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await message.answer("📢 Guruhlarni boshqarish bo'limi:", reply_markup=guruh_boshqarish_keyboard())


@router.message(F.text == "🔍 Kod bo'yicha qidirish")
async def kod_qidirish_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    await state.set_state(KodQidirish.kod_kutish)
    await message.answer("🔍 Qidirmoqchi bo'lgan o'quvchi kodini kiriting:")


@router.message(KodQidirish.kod_kutish)
async def kod_qidirish_process(message: Message, state: FSMContext):
    if not await admin_tekshir(state, message.from_user.id): return
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer("❌ O'quvchi topilmadi.")
    else:
        text = (
            f"👤 <b>O'quvchi ma'lumotlari:</b>\n\n"
            f"🆔 Kod: <b>{talaba['kod']}</b>\n"
            f"👤 Ism: <b>{talaba['ismlar']}</b>\n"
            f"🏫 Sinf: <b>{talaba['sinf']}</b>\n"
            f"🎯 Yo'nalish: <b>{talaba['yonalish']}</b>\n"
            f"🏆 Ball: <b>{talaba['umumiy_ball']}</b>"
        )
        await message.answer(text, parse_mode="HTML")
    await state.set_state(None)
