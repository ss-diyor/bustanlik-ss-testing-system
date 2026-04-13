import os
import re
import matplotlib.pyplot as plt
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import talaba_topish, talaba_natijalari, get_all_user_ids, kalit_ol
from keyboards import user_menu_keyboard, murojaat_bekor_qilish_keyboard, murojaat_javob_keyboard, test_tanlash_keyboard
from config import ADMIN_IDS

router = Router()

# ─────────────────────────────────────────
# FSM holatlari
# ─────────────────────────────────────────

class MurojaatState(StatesGroup):
    xabar_kutish = State()

class TestCheckState(StatesGroup):
    javob_kutish = State()

ADMIN_TUGMALAR = {
    "➕ O'quvchi qo'shish",
    "📥 Exceldan import",
    "🔑 Test kalitlarini boshqarish",
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
    "✅ Javoblarni tekshirish"
}

# ─────────────────────────────────────────
# Admin bilan bog'lanish
# ─────────────────────────────────────────

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

# ─────────────────────────────────────────
# Javoblarni tekshirish (Xato ustida ishlash)
# ─────────────────────────────────────────

@router.message(F.text == "✅ Javoblarni tekshirish")
async def check_start(message: Message):
    kb = test_tanlash_keyboard()
    if not kb:
        await message.answer("⚠️ Hozirda tekshirish uchun ochiq testlar mavjud emas.")
        return
    await message.answer("📝 Qaysi test bo'yicha javoblaringizni tekshirmoqchisiz?", reply_markup=kb)


@router.callback_query(F.data.startswith("check_test:"))
async def check_test_selected(callback: CallbackQuery, state: FSMContext):
    test_nomi = callback.data.split(":")[1]
    await state.update_data(check_test_nomi=test_nomi)
    await state.set_state(TestCheckState.javob_kutish)
    await callback.message.edit_text(
        f"✅ Test: <b>{test_nomi}</b>\n\n"
        f"Endi javoblaringizni quyidagi formatda yuboring:\n"
        f"<code>1A2B3C...</code> yoki <code>ABCD...</code>\n\n"
        f"<i>Masalan: 1A2C3B... yoki faqat harflar ABC...</i>",
        parse_mode="HTML"
    )


@router.message(TestCheckState.javob_kutish)
async def process_answers(message: Message, state: FSMContext):
    if message.text in ADMIN_TUGMALAR:
        await state.clear()
        return

    user_input = message.text.strip().upper()
    data = await state.get_data()
    test_nomi = data.get("check_test_nomi")
    
    test_info = kalit_ol(test_nomi)
    if not test_info:
        await message.answer("❌ Xatolik: Test ma'lumotlari topilmadi.")
        await state.clear()
        return

    original_kalitlar = test_info['kalitlar']
    
    def parse_keys(text):
        if any(char.isdigit() for char in text):
            found = re.findall(r'\d+([A-Z])', text)
            if found: return "".join(found)
        return "".join(re.findall(r'[A-Z]', text))

    clean_kalit = parse_keys(original_kalitlar)
    clean_user = parse_keys(user_input)

    if not clean_user:
        await message.answer("❌ Javoblar formati noto'g'ri. Iltimos, 1A2B... yoki ABCD... formatida yuboring.")
        return

    correct_count = 0
    wrong_answers = []
    
    total_questions = len(clean_kalit)
    user_len = len(clean_user)
    
    for i in range(min(total_questions, user_len)):
        if clean_kalit[i] == clean_user[i]:
            correct_count += 1
        else:
            wrong_answers.append(f"<b>{i+1}</b>-savol: Siz: <code>{clean_user[i]}</code> | To'g'ri: <code>{clean_kalit[i]}</code>")

    result_text = (
        f"📊 <b>Test natijangiz: {test_nomi}</b>\n\n"
        f"✅ To'g'ri javoblar: <b>{correct_count}</b> ta\n"
        f"❌ Xato javoblar: <b>{user_len - correct_count}</b> ta\n"
        f"🏁 Jami savollar: <b>{total_questions}</b> ta\n"
        f"📈 Foiz: <b>{round((correct_count/total_questions)*100, 1) if total_questions > 0 else 0}%</b>\n\n"
    )

    if wrong_answers:
        result_text += "🔍 <b>Xatolar ro'yxati:</b>\n"
        for wa in wrong_answers[:20]:
            result_text += f"• {wa}\n"
        if len(wrong_answers) > 20:
            result_text += f"\n<i>...va yana {len(wrong_answers)-20} ta xato.</i>"
    else:
        result_text += "🎉 <b>Ajoyib! Hech qanday xato qilmadingiz!</b>"

    await message.answer(result_text, parse_mode="HTML", reply_markup=user_menu_keyboard())
    await state.clear()

# ─────────────────────────────────────────
# Natijani ko'rish
# ─────────────────────────────────────────

@router.message(F.text & ~F.text.startswith("/"))
async def talaba_natija(message: Message, state: FSMContext):
    if message.text in ADMIN_TUGMALAR:
        return

    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)

    if not talaba:
        await message.answer(
            f"❌ <b>{kod}</b> kodi topilmadi.\n\n"
            f"Iltimos, kodingizni to'g'ri kiriting.\n"
            f"Masalan: <code>A-001</code> yoki <code>52B</code>",
            parse_mode="HTML"
        )
        return

    natijalar = talaba_natijalari(kod)
    if not natijalar:
        await message.answer(f"👤 <b>{talaba['ismlar']}</b>\n\n⚠️ Siz uchun hali test natijalari kiritilmagan.", parse_mode="HTML")
        return

    songi = natijalar[0]
    foiz = round((songi['umumiy_ball'] / 189) * 100, 1)

    text = (
        f"🎓 <b>Sizning natijangiz (Oxirgi test)</b>\n\n"
        f"👤 Ism: <b>{talaba['ismlar']}</b>\n"
        f"🆔 Kod: <b>{talaba['kod']}</b>\n"
        f"🏫 Sinf: <b>{talaba['sinf']}</b>\n"
        f"🎯 Yo'nalish: <b>{talaba['yonalish']}</b>\n\n"
        f"📊 <b>Fan bo'yicha natijalar:</b>\n"
        f"  📘 Majburiy fanlar: {songi['majburiy']}/30 ta → <b>{songi['majburiy'] * 1.1:.1f}</b> ball\n"
        f"  📗 1-asosiy fan:    {songi['asosiy_1']}/30 ta → <b>{songi['asosiy_1'] * 3.1:.1f}</b> ball\n"
        f"  📙 2-asosiy fan:    {songi['asosiy_2']}/30 ta → <b>{songi['asosiy_2'] * 2.1:.1f}</b> ball\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Umumiy ball: {songi['umumiy_ball']} / 189</b>\n"
        f"📈 Foiz: <b>{foiz}%</b>\n"
        f"📅 Sana: {songi['test_sanasi']}\n\n"
    )

    if len(natijalar) > 1:
        text += "📜 <b>Oldingi natijalar:</b>\n"
        for n in natijalar[1:6]:
            text += f"• {n['test_sanasi'][:10]}: <b>{n['umumiy_ball']}</b> ball\n"
        
        try:
            plot_path = f"plot_{kod}.png"
            dates = [n['test_sanasi'][:10] for n in reversed(natijalar[:10])]
            scores = [n['umumiy_ball'] for n in reversed(natijalar[:10])]
            
            plt.figure(figsize=(8, 4))
            plt.plot(dates, scores, marker='o', linestyle='-', color='b')
            plt.title(f"{talaba['ismlar']} - Natijalar Dinamikasi")
            plt.xlabel("Sana")
            plt.ylabel("Ball")
            plt.grid(True)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(plot_path)
            plt.close()
            
            await message.answer_photo(FSInputFile(plot_path), caption=text, parse_mode="HTML")
            os.remove(plot_path)
            return
        except:
            pass

    await message.answer(text, parse_mode="HTML")
