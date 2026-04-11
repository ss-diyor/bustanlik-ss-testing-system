import os
import matplotlib.pyplot as plt
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import talaba_topish, talaba_natijalari, get_all_user_ids, talaba_barcha_natijalari
from keyboards import user_menu_keyboard, murojaat_bekor_qilish_keyboard, murojaat_javob_keyboard
from config import ADMIN_IDS
from certificate import CertificateGenerator

router = Router()

# Admin tugmalari ro'yxati — student handler bularni ushlamamasligi kerak
class MurojaatState(StatesGroup):
    xabar_kutish = State()

ADMIN_TUGMALAR = {
    "➕ O'quvchi qo'shish",
    "📥 Exceldan import",
    "✏️ Natijani tahrirlash",
    "⚙️ Yo'nalishlarni boshqarish",
    "🏫 Sinflarni boshqarish",
    "📊 Statistika",
    "📋 O'quvchilar ro'yxati",
    "📥 Excelga yuklash",
    "🧹 Bazani tozalash",
    "📢 Xabar yuborish",
    "🔍 Kod bo'yicha qidirish",
    "🚪 Chiqish",
    "✍️ Admin bilan bog'lanish",
    "❌ Bekor qilish",
    "📊 Mening natijalarim",
}

class ShaxsiyKabinet(StatesGroup):
    kod_kutish = State()


@router.message(F.text == "✍️ Admin bilan bog'lanish")
async def murojaat_boshlash(message: Message, state: FSMContext):
    await state.set_state(MurojaatState.xabar_kutish)
    await message.answer(
        "📝 <b>Murojaatingizni yozib yuboring.</b>\n\n"
        "Adminlarimiz tez orada sizga javob berishadi.",
        parse_mode="HTML",
        reply_markup=murojaat_bekor_qilish_keyboard()
    )

@router.message(MurojaatState.xabar_kutish)
async def murojaat_yuborish(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("❌ Murojaat bekor qilindi.", reply_markup=user_menu_keyboard())
        return

    # Murojaatni barcha adminlarga yuborish
    murojaat_matni = (
        f"📩 <b>Yangi murojaat keldi!</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {message.from_user.full_name}\n"
        f"🆔 <b>ID:</b> <code>{message.from_user.id}</code>\n"
        f"🔗 <b>Username:</b> @{message.from_user.username if message.from_user.username else 'yoq'}\n\n"
        f"📝 <b>Murojaat matni:</b>\n{message.html_text}"
    )

    sent_to_admin = False
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id, 
                murojaat_matni, 
                reply_markup=murojaat_javob_keyboard(message.from_user.id),
                parse_mode="HTML"
            )
            sent_to_admin = True
        except Exception:
            continue

    if sent_to_admin:
        await message.answer(
            "✅ <b>Murojaatingiz adminga yuborildi!</b>\n\n"
            "Tez orada javob olasiz.",
            parse_mode="HTML",
            reply_markup=user_menu_keyboard()
        )
    else:
        await message.answer(
            "⚠️ <b>Xatolik yuz berdi!</b>\n\n"
            "Hozirda adminlar bilan bog'lanish imkoni yo'q. Iltimos, keyinroq urinib ko'ring.",
            parse_mode="HTML",
            reply_markup=user_menu_keyboard()
        )
    
    await state.clear()

@router.message(F.text == "📊 Mening natijalarim")
async def shaxsiy_kabinet_start(message: Message, state: FSMContext):
    await state.set_state(ShaxsiyKabinet.kod_kutish)
    await message.answer("📊 **Shaxsiy kabinetingizga kirish uchun kodingizni kiriting:**\n(Masalan: 1001)", parse_mode="HTML")

@router.message(ShaxsiyKabinet.kod_kutish)
async def shaxsiy_kabinet_view(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer(f"❌ **{kod}** kodi topilmadi.", parse_mode="HTML")
        await state.clear()
        return

    natijalar = talaba_barcha_natijalari(kod)
    if not natijalar:
        await message.answer(f"👤 **{talaba['ismlar']}**\n\n⚠️ Siz uchun hali test natijalari kiritilmagan.", parse_mode="HTML")
        await state.clear()
        return

    songi = natijalar[-1]
    foiz = round((songi['umumiy_ball'] / 189) * 100, 1)

    text = (
        f"👤 **O'quvchi:** {talaba['ismlar']}\n"
        f"🆔 **Kod:** {talaba['kod']}\n"
        f"🏫 **Sinf:** {talaba['sinf']}\n"
        f"🎯 **Yo'nalish:** {talaba['yonalish']}\n\n"
        f"📊 **Oxirgi natija:**\n"
        f"   Majburiy: {songi['majburiy']} ta\n"
        f"   Asosiy 1: {songi['asosiy_1']} ta\n"
        f"   Asosiy 2: {songi['asosiy_2']} ta\n"
        f"🏆 **Umumiy ball: {songi['umumiy_ball']}**\n"
        f"📈 **Foiz: {foiz}%**\n\n"
    )

    # Tarix va Dinamika
    if len(natijalar) > 1:
        text += "📜 **Natijalar tarixi:**\n"
        for n in reversed(natijalar[-5:]):
            text += f"• {n['test_sanasi'][:10]}: **{n['umumiy_ball']}** ball\n"
        
        # Dinamika grafigi
        try:
            plot_path = f"dynamic_{kod}.png"
            dates = [n['test_sanasi'][:10] for n in natijalar[-10:]]
            scores = [n['umumiy_ball'] for n in natijalar[-10:]]
            plt.figure(figsize=(8, 4))
            plt.plot(dates, scores, marker='o', color='green')
            plt.title("Natijalar Dinamikasi")
            plt.grid(True)
            plt.savefig(plot_path)
            plt.close()
            await message.answer_photo(FSInputFile(plot_path))
            os.remove(plot_path)
        except Exception as e:
            print(f"Grafik xatosi: {e}")

    # Sertifikat (masalan, 100 balldan yuqori bo'lsa)
    if songi['umumiy_ball'] >= 100:
        try:
            gen = CertificateGenerator()
            cert_path = gen.generate(talaba['ismlar'], songi['umumiy_ball'], songi['test_sanasi'][:10], kod)
            await message.answer_document(FSInputFile(cert_path), caption="🏆 Yuqori natijangiz uchun sertifikat!")
            os.remove(cert_path)
        except Exception as e:
            print(f"Sertifikat xatosi: {e}")

    await message.answer(text, parse_mode="HTML", reply_markup=user_menu_keyboard())
    await state.clear()

@router.message(F.text & ~F.text.startswith("/"))
async def talaba_natija_quick(message: Message, state: FSMContext):
    if message.text in ADMIN_TUGMALAR:
        return
    # Tezkor natija ko'rish (avvalgi mantiqni saqlab qolamiz)
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer(f"❌ **{kod}** topilmadi.", parse_mode="HTML")
        return
    natijalar = talaba_natijalari(kod)
    if not natijalar:
        await message.answer("⚠️ Natijalar topilmadi.", parse_mode="HTML")
        return
    songi = natijalar[0]
    await message.answer(f"📊 **{talaba['ismlar']}**\n\nBall: **{songi['umumiy_ball']}**\nSana: {songi['test_sanasi']}", parse_mode="HTML")
