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
    sinf_ol, sinf_qosh, sinf_ochir, talaba_songi_natija,
    kalit_qosh, kalit_ol, kalit_tahrirla, kalit_holat_ozgartir, kalit_ochir,
    talaba_user_id_ol
)
from keyboards import (
    admin_menu_keyboard, yonalish_keyboard, tasdiqlash_keyboard,
    yonalish_boshqarish_keyboard, yonalish_ochirish_keyboard,
    sinf_keyboard, sinf_boshqarish_keyboard, sinf_ochirish_keyboard,
    kalit_boshqarish_keyboard, kalit_actions_keyboard, kalit_yonalish_tanlash_keyboard
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

class NatijaTahrirlash(StatesGroup):
    kod_kutish = State()
    majburiy_kutish = State()
    asosiy1_kutish = State()
    asosiy2_kutish = State()

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

async def bildirishnoma_yuborish(bot: Bot, talaba_kod: str, natija: dict, talaba: dict):
    """
    Talabaning Telegram user_id si bo'lsa, yangi natija haqida xabar yuboradi.
    Sertifikat ham generatsiya qilinadi.
    """
    user_id = talaba_user_id_ol(talaba_kod)
    if not user_id:
        return  # Talaba profilini ulamagan — bildirishnoma yo'q

    foiz = round((natija['umumiy_ball'] / 189) * 100, 1)
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
        f"📜 Quyida sizning natijangiz aks etgan sertifikat biriktirilgan."
    )
    
    # Sertifikat yaratish
    try:
        cert_gen = CertificateGenerator()
        sana = str(natija.get('test_sanasi', 'Noaniq'))[:10]
        cert_path = cert_gen.generate(talaba['ismlar'], natija['umumiy_ball'], sana, talaba['kod'])
        
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
# Test Kalitlarini Boshqarish (Yo'nalishga bog'liq)
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
            await callback.message.edit_text("⚠️ Hozircha kalitlar yo'q.", reply_markup=kalit_boshqarish_keyboard())
        else:
            text = "📋 <b>Mavjud test kalitlari:</b>\n\nTanlang:"
            buttons = []
            for k in kalitlar:
                status = "🟢" if k['holat'] == 'ochiq' else "🔴"
                yon_label = f" [{k['yonalish']}]" if k.get('yonalish') else " [Umumiy]"
                buttons.append([InlineKeyboardButton(
                    text=f"{status} {k['test_nomi']}{yon_label}",
                    callback_data=f"kalit_view:{k['test_nomi']}"
                )])
            buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="kalit_boshqar:orqaga")])
            await callback.message.edit_text(text, parse_mode="HTML",
                                             reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    elif action == "qosh":
        # Umumiy kalit (yo'nalishsiz)
        await state.set_state(KalitBoshqar.nomi_kutish)
        await callback.message.edit_text("📝 Test nomini kiriting (masalan: 15-may test):")

    elif action == "yonalish_qosh":
        # Yo'nalishga bog'liq kalit — avval yo'nalish tanlanadi
        await callback.message.edit_text(
            "🎯 Qaysi yo'nalish uchun kalit qo'shmoqchisiz?\nYo'nalishni tanlang:",
            reply_markup=kalit_yonalish_tanlash_keyboard()
        )

    elif action == "orqaga":
        await state.set_state(None)
        await callback.message.answer("Asosiy menyu:", reply_markup=admin_menu_keyboard())


# Yo'nalish tanlandi — test nomini so'raymiz
@router.callback_query(F.data.startswith("kalit_yon:"))
async def kalit_yonalish_tanlandi(callback: CallbackQuery, state: FSMContext):
    yonalish = callback.data.split(":", 1)[1]
    # To'liq yo'nalish nomini topamiz (truncate bo'lishi mumkin)
    barcha = yonalish_ol()
    mos = next((y for y in barcha if y.startswith(yonalish)), yonalish)
    await state.update_data(kalit_yonalish=mos)
    await state.set_state(KalitBoshqar.yonalish_nomi_kutish)
    await callback.message.edit_text(
        f"🎯 Yo'nalish: <b>{mos}</b>\n\n📝 Test nomini kiriting (masalan: 15-may test):",
        parse_mode="HTML"
    )


@router.message(KalitBoshqar.yonalish_nomi_kutish)
async def kalit_yonalish_nomi_kutish(message: Message, state: FSMContext):
    nomi = message.text.strip()
    await state.update_data(test_nomi=nomi)
    await state.set_state(KalitBoshqar.yonalish_kalit_kutish)
    data = await state.get_data()
    await message.answer(
        f"✅ Test nomi: <b>{nomi}</b>\n"
        f"🎯 Yo'nalish: <b>{data.get('kalit_yonalish')}</b>\n\n"
        f"Endi kalitlarni kiriting (Format: 1A2B3C... yoki ABCDE...):",
        parse_mode="HTML"
    )


@router.message(KalitBoshqar.yonalish_kalit_kutish)
async def kalit_yonalish_saqla(message: Message, state: FSMContext):
    kalitlar = message.text.strip().upper()
    data = await state.get_data()
    if kalit_qosh(data['test_nomi'], kalitlar, yonalish=data.get('kalit_yonalish')):
        await message.answer(
            f"✅ <b>{data['test_nomi']}</b> kaliti saqlandi!\n"
            f"🎯 Yo'nalish: <b>{data.get('kalit_yonalish')}</b>",
            parse_mode="HTML", reply_markup=admin_menu_keyboard()
        )
    else:
        await message.answer("❌ Bu nomli test allaqachon mavjud.")
    await state.set_state(None)


# Umumiy kalit (yo'nalishsiz)
@router.message(KalitBoshqar.nomi_kutish)
async def kalit_nomi_kutish(message: Message, state: FSMContext):
    nomi = message.text.strip()
    await state.update_data(test_nomi=nomi, kalit_yonalish=None)
    await state.set_state(KalitBoshqar.kalit_kutish)
    await message.answer(
        f"✅ Test nomi: <b>{nomi}</b>\n\nKalitlarni kiriting (Format: 1A2B3C... yoki ABCDE...):",
        parse_mode="HTML"
    )


@router.message(KalitBoshqar.kalit_kutish)
async def kalit_saqla(message: Message, state: FSMContext):
    kalitlar = message.text.strip().upper()
    data = await state.get_data()
    if kalit_qosh(data['test_nomi'], kalitlar, yonalish=None):
        await message.answer(
            f"✅ <b>{data['test_nomi']}</b> uchun umumiy kalit saqlandi!",
            parse_mode="HTML", reply_markup=admin_menu_keyboard()
        )
    else:
        await message.answer("❌ Bu nomli test allaqachon mavjud.")
    await state.set_state(None)


@router.callback_query(F.data.startswith("kalit_view:"))
async def kalit_view(callback: CallbackQuery):
    test_nomi = callback.data.split(":", 1)[1]
    k = kalit_ol(test_nomi)
    if not k:
        await callback.answer("❌ Kalit topilmadi.")
        return
    yon_text = k.get('yonalish') or "Umumiy (barcha yo'nalishlar)"
    text = (
        f"📋 <b>Test:</b> {k['test_nomi']}\n"
        f"🎯 <b>Yo'nalish:</b> {yon_text}\n"
        f"🔑 <b>Kalitlar:</b> <code>{k['kalitlar']}</code>\n"
        f"📊 <b>Holat:</b> {k['holat'].upper()}"
    )
    await callback.message.edit_text(text, parse_mode="HTML",
                                     reply_markup=kalit_actions_keyboard(test_nomi, k['holat']))


@router.callback_query(F.data.startswith("kalit_status:"))
async def kalit_status_change(callback: CallbackQuery):
    test_nomi = callback.data.split(":", 1)[1]
    k = kalit_ol(test_nomi)
    yangi_holat = "yopiq" if k['holat'] == "ochiq" else "ochiq"
    kalit_holat_ozgartir(test_nomi, yangi_holat)
    await callback.answer(f"✅ Holat {yangi_holat}ga o'zgartirildi")
    await kalit_view(callback)


@router.callback_query(F.data.startswith("kalit_edit:"))
async def kalit_edit_start(callback: CallbackQuery, state: FSMContext):
    test_nomi = callback.data.split(":", 1)[1]
    await state.update_data(edit_test_nomi=test_nomi)
    await state.set_state(KalitBoshqar.edit_kalit_kutish)
    await callback.message.answer(f"📝 <b>{test_nomi}</b> uchun yangi kalitlarni kiriting:", parse_mode="HTML")
    await callback.answer()


@router.message(KalitBoshqar.edit_kalit_kutish)
async def kalit_edit_save(message: Message, state: FSMContext):
    yangi_kalitlar = message.text.strip().upper()
    data = await state.get_data()
    kalit_tahrirla(data['edit_test_nomi'], yangi_kalitlar)
    await message.answer(f"✅ <b>{data['edit_test_nomi']}</b> kalitlari yangilandi!",
                         parse_mode="HTML", reply_markup=admin_menu_keyboard())
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
        if talaba and yangi_natija:
            await bildirishnoma_yuborish(callback.bot, data["kod"], yangi_natija, talaba)

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
        await bildirishnoma_yuborish(message.bot, data["tahrir_kod"], yangi_natija, talaba)

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
                        await bildirishnoma_yuborish(message.bot, kod, yangi_natija, talaba)
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
    if not await admin_tekshir(state): return
    s = statistika()
    if not s:
        await message.answer("⚠️ Ma'lumotlar mavjud emas.")
        return
    text = (
        "📊 <b>Umumiy statistika:</b>\n\n"
        f"👥 O'quvchilar soni: <b>{s['jami']} ta</b>\n"
        f"📈 O'rtacha ball: <b>{s['ortacha']}</b>\n"
        f"🏆 Eng yuqori ball: <b>{s['eng_yuqori']}</b>\n"
        f"📉 Eng past ball: <b>{s['eng_past']}</b>"
    )
    await message.answer(text, parse_mode="HTML")

# ─────────────────────────────────────────
# O'quvchilar ro'yxati
# ─────────────────────────────────────────

@router.message(F.text == "📋 O'quvchilar ro'yxati")
async def admin_list(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    talabalar = talaba_hammasi()
    if not talabalar:
        await message.answer("⚠️ Ro'yxat bo'sh.")
        return
    text = "📋 <b>O'quvchilar ro'yxati:</b>\n\n"
    for i, t in enumerate(talabalar, 1):
        text += f"{i}. {t['kod']} | {t['sinf']} | {t['umumiy_ball'] if t['umumiy_ball'] else 0} ball\n"
        if i % 50 == 0:
            await message.answer(text, parse_mode="HTML")
            text = ""
    if text:
        await message.answer(text, parse_mode="HTML")

# ─────────────────────────────────────────
# Excelga yuklash
# ─────────────────────────────────────────

@router.message(F.text == "📥 Excelga yuklash")
async def admin_excel(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    data = get_all_students_for_excel()
    if not data:
        await message.answer("⚠️ Ma'lumotlar yo'q.")
        return
    df = pd.DataFrame(data)
    df.columns = ["Kod", "Sinf", "Yo'nalish", "Ism", "Majburiy", "Asosiy-1", "Asosiy-2", "Umumiy Ball", "Vaqt"]
    file_path = "dtm_natijalar.xlsx"
    df.to_excel(file_path, index=False)
    await message.answer_document(FSInputFile(file_path), caption="📊 Barcha natijalar Excel formatida.")

# ─────────────────────────────────────────
# Bazani tozalash
# ─────────────────────────────────────────

@router.message(F.text == "🧹 Bazani tozalash")
async def clear_db_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await state.set_state(ConfirmDelete.tasdiqlash_kutish)
    await message.answer(
        "⚠️ <b>DIQQAT!</b>\nBarcha o'quvchi va natijalarni o'chirib tashlamoqchimisiz?\n\n"
        "Tasdiqlash uchun <b>HA</b> deb yozing:",
        parse_mode="HTML"
    )


@router.message(ConfirmDelete.tasdiqlash_kutish)
async def clear_db_confirm(message: Message, state: FSMContext):
    if message.text.strip().upper() == "HA":
        delete_all_data()
        await message.answer("✅ Baza tozalandi.")
    else:
        await message.answer("❌ Bekor qilindi.")
    await state.set_state(None)

# ─────────────────────────────────────────
# Xabar yuborish (Broadcast)
# ─────────────────────────────────────────

@router.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await state.set_state(Broadcast.xabar_kutish)
    await message.answer("📢 Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:")


@router.message(Broadcast.xabar_kutish)
async def broadcast_send(message: Message, state: FSMContext):
    user_ids = get_all_user_ids()
    count = 0
    for uid in user_ids:
        try:
            await message.copy_to(uid)
            count += 1
            await asyncio.sleep(0.05)
        except Exception:
            pass
    await message.answer(f"✅ Xabar {count} ta foydalanuvchiga yuborildi.")
    await state.set_state(None)

# ─────────────────────────────────────────
# Kod bo'yicha qidirish
# ─────────────────────────────────────────

@router.message(F.text == "🔍 Kod bo'yicha qidirish")
async def search_start(message: Message, state: FSMContext):
    if not await admin_tekshir(state): return
    await state.set_state(KodQidirish.kod_kutish)
    await message.answer("🔍 Qidirilayotgan o'quvchi kodini kiriting:")


@router.message(KodQidirish.kod_kutish)
async def search_kod(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer(f"❌ {kod} topilmadi.")
    else:
        natija = talaba_songi_natija(kod)
        ball_text = natija['umumiy_ball'] if natija else "Natija yo'q"
        ulangan_text = "Ha" if talaba.get('user_id') else "Yo'q"
        text = (
            f"🔍 <b>Ma'lumot topildi:</b>\n\n"
            f"👤 Ism: <b>{talaba['ismlar']}</b>\n"
            f"🆔 Kod: <b>{talaba['kod']}</b>\n"
            f"🏫 Sinf: <b>{talaba['sinf']}</b>\n"
            f"🎯 Yo'nalish: <b>{talaba['yonalish']}</b>\n"
            f"📊 Ball: <b>{ball_text}</b>\n"
            f"🔗 Ulangan: <b>{ulangan_text}</b>"
        )
        await message.answer(text, parse_mode="HTML")
    await state.set_state(None)

# ─────────────────────────────────────────
# Murojaatga javob berish
# ─────────────────────────────────────────

@router.callback_query(F.data.startswith("murojaat_javob:"))
async def murojaat_javob_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.data.split(":")[1]
    await state.update_data(reply_to=user_id)
    await state.set_state(MurojaatJavob.javob_kutish)
    await callback.message.answer(f"✍️ Foydalanuvchi (ID: {user_id}) uchun javobingizni yozing:")
    await callback.answer()


@router.message(MurojaatJavob.javob_kutish)
async def murojaat_javob_send(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_to")
    javob_matni = (
        f"📩 <b>Admin sizning murojaatingizga javob berdi:</b>\n\n"
        f"{message.html_text}"
    )
    try:
        await message.bot.send_message(user_id, javob_matni, parse_mode="HTML")
        await message.answer("✅ Javob yuborildi.")
    except Exception as e:
        await message.answer(f"❌ Yuborishda xatolik: {e}")
    await state.set_state(None)
