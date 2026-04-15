import os
import re
import asyncio
import matplotlib
matplotlib.use("Agg")  # GUI yo'q muhitda xatolikni oldini oladi
import matplotlib.pyplot as plt
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    talaba_topish, talaba_natijalari, get_all_user_ids, kalit_ol,
    get_top_10_in_class, get_overall_ranking, get_student_rank,
    get_avg_score_by_direction, get_class_comparison, get_most_improved_students,
    get_score_difference, get_setting, check_access, add_access_request, get_request_by_user
)
from keyboards import (
    user_menu_keyboard, murojaat_bekor_qilish_keyboard, murojaat_javob_keyboard,
    test_tanlash_keyboard, ranking_keyboard, stats_keyboard
)
from config import ADMIN_IDS
from certificate import CertificateGenerator

router = Router()

# ─────────────────────────────────────────
# FSM holatlari
# ─────────────────────────────────────────

class MurojaatState(StatesGroup):
    xabar_kutish = State()

class TestCheckState(StatesGroup):
    javob_kutish = State()

class ResultCheckState(StatesGroup):
    kod_kutish = State()

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
    "✅ Javoblarni tekshirish",
    "📊 Mening natijalarim"
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
            "✅ <b>Murojaatingiz adminga yuborildi!</b>\n\nTez orada javob olasiz.",
            parse_mode="HTML",
            reply_markup=user_menu_keyboard()
        )
    else:
        await message.answer(
            "⚠️ <b>Xatolik yuz berdi!</b>\n\nHozirda adminlar bilan bog'lanish imkoni yo'q.",
            parse_mode="HTML",
            reply_markup=user_menu_keyboard()
        )

    await state.clear()

# ─────────────────────────────────────────
# Javoblarni tekshirish
# ─────────────────────────────────────────

@router.message(F.text == "✅ Javoblarni tekshirish")
async def check_start(message: Message, state: FSMContext):
    # Talabaning yo'nalishini aniqlaymiz (agar ULASH_ qilingan bo'lsa)
    yonalish = None
    # Foydalanuvchi user_id si bo'yicha talabani topamiz
    from database import get_connection, release_connection
    import psycopg2.extras
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT yonalish FROM talabalar WHERE user_id = %s", (message.from_user.id,))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    if row:
        yonalish = row["yonalish"]

    kb = test_tanlash_keyboard(yonalish=yonalish)
    if not kb:
        await message.answer("⚠️ Hozirda tekshirish uchun ochiq testlar mavjud emas.")
        return
    await message.answer("📝 Qaysi test bo'yicha javoblaringizni tekshirmoqchisiz?", reply_markup=kb)


@router.callback_query(F.data.startswith("check_test:"))
async def check_test_selected(callback: CallbackQuery, state: FSMContext):
    test_nomi = callback.data.split(":", 1)[1]
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
            if found:
                return "".join(found)
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
            wrong_answers.append(
                f"<b>{i+1}</b>-savol: Siz: <code>{clean_user[i]}</code> | To'g'ri: <code>{clean_kalit[i]}</code>"
            )

    result_text = (
        f"📊 <b>Test natijangiz: {test_nomi}</b>\n\n"
        f"✅ To'g'ri javoblar: <b>{correct_count}</b> ta\n"
        f"❌ Xato javoblar: <b>{user_len - correct_count}</b> ta\n"
        f"🏁 Jami savollar: <b>{total_questions}</b> ta\n"
        f"📈 Foiz: <b>{round((correct_count / total_questions) * 100, 1) if total_questions > 0 else 0}%</b>\n\n"
    )

    if wrong_answers:
        result_text += "🔍 <b>Xatolar ro'yxati:</b>\n"
        for wa in wrong_answers[:20]:
            result_text += f"• {wa}\n"
        if len(wrong_answers) > 20:
            result_text += f"\n<i>...va yana {len(wrong_answers) - 20} ta xato.</i>"
    else:
        result_text += "🎉 <b>Ajoyib! Hech qanday xato qilmadingiz!</b>"

    await message.answer(result_text, parse_mode="HTML", reply_markup=user_menu_keyboard())
    await state.clear()

# ─────────────────────────────────────────
# Reyting tizimi
# ─────────────────────────────────────────

@router.message(F.text == "🏆 Reyting")
async def ranking_menu(message: Message):
    if get_setting('ranking_enabled', 'True') == 'False':
        await message.answer("⚠️ Reyting tizimi vaqtincha o'chirib qo'yilgan.")
        return
    await message.answer("🏆 <b>Reyting tizimi:</b>\n\nQuyidagilardan birini tanlang:", parse_mode="HTML", reply_markup=ranking_keyboard())

@router.callback_query(F.data.startswith("ranking:"))
async def ranking_process(callback: CallbackQuery):
    action = callback.data.split(":")[1]
    
    # Talabani user_id orqali topish
    from database import get_connection, release_connection
    import psycopg2.extras
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM talabalar WHERE user_id = %s", (callback.from_user.id,))
    talaba = cur.fetchone()
    cur.close()
    release_connection(conn)

    if action == "class_top10":
        if not talaba or not talaba['sinf']:
            await callback.answer("⚠️ Avval profilingizni ulashing (Masalan: ULASH_A-001)", show_alert=True)
            return
        
        top10 = get_top_10_in_class(talaba['sinf'])
        if not top10:
            await callback.answer("⚠️ Hozircha natijalar yo'q.", show_alert=True)
            return
        
        text = f"🔝 <b>{talaba['sinf']} sinfining Top 10 o'quvchilari:</b>\n\n"
        for i, t in enumerate(top10, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            # Anonimlik: Faqat o'zini ismini ko'radi, boshqalarni "O'quvchi" deb ko'radi
            ismlar = t['ismlar'] if t['kod'] == talaba['kod'] else f"O'quvchi #{t['kod'][-3:]}"
            text += f"{emoji} {ismlar} — <b>{t['umumiy_ball']}</b> ball\n"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=ranking_keyboard())

    elif action == "overall_top50":
        if not check_access(callback.from_user.id):
            # Ruxsat yo'q bo'lsa, so'rov yuborish tugmasini ko'rsatish
            req = get_request_by_user(callback.from_user.id)
            if req and req['status'] == 'pending':
                await callback.answer("⏳ So'rovingiz ko'rib chiqilmoqda. Admin javobini kuting.", show_alert=True)
                return
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔔 Ruxsat so'rash", callback_data="request_overall_access")],
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="ranking:back")]
            ])
            await callback.message.edit_text("⚠️ Umumiy reytingni ko'rish uchun admindan ruxsat olishingiz kerak.", reply_markup=kb)
            return

        top50 = get_overall_ranking()
        if not top50:
            await callback.answer("⚠️ Hozircha natijalar yo'q.", show_alert=True)
            return
        
        text = "🌍 <b>Umumiy Top 50 o'quvchilar:</b>\n\n"
        for i, t in enumerate(top50, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            # Ruxsat olingan bo'lsa ismlarni ko'rsatish mumkin yoki baribir anonim saqlash (mijoz talabiga ko'ra ruxsat olinganda ko'rinadi)
            text += f"{emoji} {t['ismlar']} ({t['sinf']}) — <b>{t['umumiy_ball']}</b> ball\n"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=ranking_keyboard())

    elif action == "my_rank":
        if not talaba:
            await callback.answer("⚠️ Avval profilingizni ulashing (Masalan: ULASH_A-001)", show_alert=True)
            return
        
        ranks = get_student_rank(talaba['kod'])
        diff = get_score_difference(talaba['kod'])
        
        text = (
            f"👤 <b>Sizning reytingingiz:</b>\n\n"
            f"👤 Ism: <b>{talaba['ismlar']}</b>\n"
            f"🏫 Sinfingizda: <b>{ranks['class']}-o'rin</b>\n"
            f"🌍 Umumiy: <b>{ranks['overall']}-o'rin</b>\n"
        )
        if diff is not None:
            if diff > 0:
                text += f"📈 O'zgarish: <b>+{diff} ball</b> (Yaxshi! 🚀)"
            elif diff < 0:
                text += f"📉 O'zgarish: <b>{diff} ball</b> (Harakat qiling! 💪)"
            else:
                text += "⏺ O'zgarish: <b>O'zgarmadi</b>"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=ranking_keyboard())

    elif action == "back":
        await callback.message.edit_text("🏆 <b>Reyting tizimi:</b>\n\nQuyidagilardan birini tanlang:", parse_mode="HTML", reply_markup=ranking_keyboard())

@router.callback_query(F.data == "request_overall_access")
async def request_overall_access_handler(callback: CallbackQuery):
    from database import get_connection, release_connection
    import psycopg2.extras
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM talabalar WHERE user_id = %s", (callback.from_user.id,))
    talaba = cur.fetchone()
    cur.close()
    release_connection(conn)
    
    if not talaba:
        await callback.answer("⚠️ Avval profilingizni ulashing (Masalan: ULASH_A-001)", show_alert=True)
        return
    
    add_access_request(callback.from_user.id, talaba['kod'])
    await callback.message.edit_text("✅ So'rovingiz adminga yuborildi. Ruxsat berilgach, sizga xabar yuboramiz.")
    
    # Adminga xabar yuborish
    from config import ADMIN_IDS
    from keyboards import request_actions_keyboard
    
    # So'rov ID sini olish
    req = get_request_by_user(callback.from_user.id)
    if req:
        admin_text = (
            f"🔔 <b>Yangi kirish so'rovi!</b>\n\n"
            f"👤 O'quvchi: <b>{talaba['ismlar']}</b>\n"
            f"🏫 Sinf: <b>{talaba['sinf']}</b>\n"
            f"🆔 Kod: <code>{talaba['kod']}</code>\n"
            f"👤 Telegram ID: <code>{callback.from_user.id}</code>"
        )
        for admin_id in ADMIN_IDS:
            try:
                await callback.bot.send_message(admin_id, admin_text, parse_mode="HTML", reply_markup=request_actions_keyboard(req['id']))
            except:
                continue
    
    await callback.answer("So'rov yuborildi")

@router.message(F.text == "📈 Statistika")
async def stats_menu(message: Message):
    if get_setting('stats_enabled', 'True') == 'False':
        await message.answer("⚠️ Statistika bo'limi vaqtincha o'chirib qo'yilgan.")
        return
    await message.answer("📈 <b>Statistika bo'limi:</b>\n\nQuyidagilardan birini tanlang:", parse_mode="HTML", reply_markup=stats_keyboard())


@router.callback_query(F.data.startswith("stats:"))
async def stats_process(callback: CallbackQuery):
    action = callback.data.split(":")[1]
    
    if action == "direction":
        data = get_avg_score_by_direction()
        if not data:
            await callback.answer("⚠️ Ma'lumotlar yo'q.", show_alert=True)
            return
        
        text = "🎯 <b>Yo'nalishlar bo'yicha o'rtacha ball:</b>\n\n"
        for i, d in enumerate(data, 1):
            text += f"{i}. {d['yonalish']}: <b>{d['avg_score']}</b>\n"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=stats_keyboard())

    elif action == "class":
        data = get_class_comparison()
        if not data:
            await callback.answer("⚠️ Ma'lumotlar yo'q.", show_alert=True)
            return
        
        text = "🏫 <b>Sinflar bo'yicha o'rtacha ball:</b>\n\n"
        for i, d in enumerate(data, 1):
            text += f"{i}. {d['sinf']}: <b>{d['avg_score']}</b>\n"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=stats_keyboard())

    elif action == "improved":
        data = get_most_improved_students()
        if not data:
            await callback.answer("⚠️ Ma'lumotlar yo'q.", show_alert=True)
            return
        
        text = "🚀 <b>Eng ko'p o'sgan o'quvchilar (Oxirgi 2 test):</b>\n\n"
        for i, d in enumerate(data, 1):
            # Statistika bo'limida ham anonimlikni saqlaymiz
            text += f"{i}. O'quvchi #{d['kod'][-3:]} ({d['sinf']}): <b>+{d['diff']} ball</b>\n"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=stats_keyboard())

# ─────────────────────────────────────────
# Natijani ko'rish
# ─────────────────────────────────────────

@router.message(F.text == "📊 Mening natijalarim")
async def results_start(message: Message, state: FSMContext):
    await state.set_state(ResultCheckState.kod_kutish)
    await message.answer(
        "📝 Natijangizni ko'rish uchun shaxsiy <b>kodingizni</b> yuboring:",
        parse_mode="HTML"
    )


@router.message(ResultCheckState.kod_kutish)
async def results_kod_olingan(message: Message, state: FSMContext):
    if message.text in ADMIN_TUGMALAR:
        await state.clear()
        return
    await state.clear()
    await _natija_yuborish(message, message.text.strip().upper())


@router.message(F.text & ~F.text.startswith("/"))
async def talaba_natija_umumiy(message: Message, state: FSMContext):
    if message.text in ADMIN_TUGMALAR:
        return
    
    # Yangi qo'shilgan tugmalarni o'tkazib yuboramiz
    if message.text in ["🏆 Reyting", "📈 Statistika"]:
        return

    current_state = await state.get_state()
    if current_state is not None:
        return
    
    # Faqat kodga o'xshash matnlarni tekshiramiz (masalan, A-001 yoki 52B)
    text = message.text.strip().upper()
    if re.match(r'^[A-Z0-9-]{2,10}$', text):
        await _natija_yuborish(message, text)


def _generate_plot(dates, scores, plot_path, ismlar):
    """Grafikni alohida thread/process'da yaratish uchun (blocking emas)."""
    plt.figure(figsize=(8, 4))
    plt.plot(dates, scores, marker='o', linestyle='-', color='b')
    plt.title(f"{ismlar} - Natijalar Dinamikasi")
    plt.xlabel("Sana")
    plt.ylabel("Ball")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()

def _generate_cert_internal(full_name, score, date, kod):
    """Sertifikatni executor'da yaratish uchun."""
    cert_gen = CertificateGenerator()
    return cert_gen.generate(full_name, score, date, kod)

async def _natija_yuborish(message: Message, kod: str):
    talaba = talaba_topish(kod)

    if not talaba:
        await message.answer(
            f"❌ <b>{kod}</b> kodi topilmadi.\n\n"
            f"Iltimos, kodingizni to'g'ri kiriting.\n"
            f"Masalan: <code>A-001</code> yoki <code>52B</code>",
            parse_mode="HTML"
        )
        return

    # Faqat oxirgi 10 ta natijani olamiz (tezlik uchun)
    natijalar = talaba_natijalari(kod, limit=10)
    if not natijalar:
        await message.answer(
            f"👤 <b>{talaba['ismlar']}</b>\n\n⚠️ Siz uchun hali test natijalari kiritilmagan.",
            parse_mode="HTML"
        )
        return

    songi = natijalar[0]
    foiz = round((songi['umumiy_ball'] / 189) * 100, 1)
    sana_str = str(songi['test_sanasi'])[:10]

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
        f"📅 Sana: {sana_str}\n\n"
    )

    loop = asyncio.get_event_loop()
    
    # 1. Sertifikat yaratish
    cert_path = None
    try:
        cert_path = await loop.run_in_executor(None, _generate_cert_internal, talaba['ismlar'], songi['umumiy_ball'], sana_str, talaba['kod'])
    except Exception as e:
        print(f"Sertifikat yaratishda xato: {e}")

    # 2. Grafik yaratish (agar natijalar 1 tadan ko'p bo'lsa)
    plot_path = f"plot_{kod}.png"
    has_plot = False
    if len(natijalar) > 1:
        text += "📜 <b>Oldingi natijalar:</b>\n"
        for n in natijalar[1:6]:
            text += f"• {str(n['test_sanasi'])[:10]}: <b>{n['umumiy_ball']}</b> ball\n"

        try:
            dates = [str(n['test_sanasi'])[:10] for n in reversed(natijalar)]
            scores = [n['umumiy_ball'] for n in reversed(natijalar)]
            await loop.run_in_executor(None, _generate_plot, dates, scores, plot_path, talaba['ismlar'])
            has_plot = True
        except Exception as e:
            print(f"Grafik chizishda xato: {e}")

    # 3. Yuborish
    try:
        if cert_path and os.path.exists(cert_path):
            # Sertifikatni hujjat sifatida yuboramiz
            await message.answer_document(FSInputFile(cert_path), caption="📜 Sizning natijangiz aks etgan sertifikat.")
            if os.path.exists(cert_path): os.remove(cert_path)
        
        if has_plot and os.path.exists(plot_path):
            # Grafikni rasm sifatida matn bilan yuboramiz
            await message.answer_photo(FSInputFile(plot_path), caption=text, parse_mode="HTML")
            if os.path.exists(plot_path): os.remove(plot_path)
        else:
            # Grafik bo'lmasa, faqat matnni yuboramiz
            await message.answer(text, parse_mode="HTML")
            
    except Exception as e:
        print(f"Yuborishda xato: {e}")
        # Xatolik bo'lsa hech bo'lmasa matnni yuboramiz
        await message.answer(text, parse_mode="HTML")
