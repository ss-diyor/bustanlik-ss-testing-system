import os
import re
import asyncio
import matplotlib
matplotlib.use("Agg")  # GUI yo'q muhitda xatolikni oldini oladi
import matplotlib.pyplot as plt
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQuery, InlineQueryResultArticle, InputTextMessageContent
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    talaba_topish, talaba_natijalari, get_all_user_ids, kalit_ol,
    get_all_in_class, get_overall_ranking, get_student_rank,
    get_avg_score_by_direction, get_class_comparison, get_most_improved_students,
    get_score_difference, get_setting, check_access, add_access_request, get_request_by_user,
    talaba_songi_natija
)
from keyboards import (
    user_menu_keyboard, murojaat_bekor_qilish_keyboard, murojaat_javob_keyboard,
    test_tanlash_keyboard, ranking_keyboard, stats_keyboard, profile_keyboard
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
# Yordamchi funksiyalar
# ─────────────────────────────────────────

def _generate_chart(natijalar, ismlar, kod):
    """O'quvchining natijalari dinamikasi grafigini chizadi."""
    if not natijalar:
        return None
    
    # Natijalarni vaqt bo'yicha tartiblaymiz (eskidan yangiga)
    sorted_results = sorted(natijalar, key=lambda x: x['test_sanasi'])
    
    dates = [str(r['test_sanasi'])[:10] for r in sorted_results]
    scores = [r['umumiy_ball'] for r in sorted_results]
    
    plt.figure(figsize=(8, 5))
    plt.plot(dates, scores, marker='o', linestyle='-', color='blue')
    plt.title(f"{ismlar} - Natijalar Dinamikasi")
    plt.xlabel("Sana")
    plt.ylabel("Ball")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    chart_path = f"charts/chart_{kod}.png"
    os.makedirs("charts", exist_ok=True)
    plt.savefig(chart_path)
    plt.close()
    return chart_path

def _generate_certificate_file(cert_gen, ismlar, ball, sana, kod):
    """Sertifikatni generatsiya qilish."""
    return cert_gen.generate(ismlar, ball, sana, kod)

async def send_full_results(message: Message, kod: str):
    """O'quvchiga barcha natijalarini (grafik, xabar va sertifikat) yuboradi."""
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer("❌ Bunday kodli o'quvchi topilmadi.")
        return

    natija = talaba_songi_natija(kod)
    if not natija:
        await message.answer(f"👤 <b>{talaba['ismlar']}</b>, sizda hali test natijalari mavjud emas.", parse_mode="HTML")
        return

    all_results = talaba_natijalari(kod)
    
    # Grafik yaratish
    chart_path = await asyncio.get_event_loop().run_in_executor(None, _generate_chart, all_results, talaba['ismlar'], kod)
    
    # Sertifikat yaratish
    cert_gen = CertificateGenerator()
    sana = str(natija.get('test_sanasi', 'Noaniq'))[:10]
    cert_path = await asyncio.get_event_loop().run_in_executor(None, _generate_certificate_file, cert_gen, talaba['ismlar'], natija['umumiy_ball'], sana, kod)

    # Xabar matni
    foiz = round((natija['umumiy_ball'] / 189) * 100, 1)
    
    matn = (
        f"🎓 <b>Sizning natijangiz (Oxirgi test)</b>\n\n"
        f"👤 Ism: <b>{talaba['ismlar']}</b>\n"
        f"🆔 Kod: <code>{talaba['kod']}</code>\n"
        f"🏫 Sinf: <b>{talaba['sinf']}</b>\n"
        f"🎯 Yo'nalish: <b>{talaba['yonalish']}</b>\n\n"
        f"📊 <b>Fan bo'yicha natijalar:</b>\n"
        f"📘 Majburiy fanlar: {natija['majburiy']}/30 ta → <b>{natija['majburiy'] * 1.1:.1f} ball</b>\n"
        f"📗 1-asosiy fan: {natija['asosiy_1']}/30 ta → <b>{natija['asosiy_1'] * 3.1:.1f} ball</b>\n"
        f"📙 2-asosiy fan: {natija['asosiy_2']}/30 ta → <b>{natija['asosiy_2'] * 2.1:.1f} ball</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Umumiy ball: {natija['umumiy_ball']} / 189</b>\n"
        f"📈 Foiz: <b>{foiz}%</b>\n"
        f"📅 Sana: <b>{sana}</b>\n\n"
        f"📜 <b>Oldingi natijalar:</b>\n"
    )
    
    # Oxirgidan boshlab natijalarni qo'shamiz
    for r in all_results[:5]:
        r_sana = str(r['test_sanasi'])[:10]
        matn += f"• {r_sana}: <b>{r['umumiy_ball']} ball</b>\n"

    # Sertifikatni rasm (grafik) bilan birga yuborish
    try:
        # 1. Sertifikatni yuboramiz
        await message.answer_document(
            FSInputFile(cert_path),
            caption="📜 Sizning natijangiz aks etgan sertifikat."
        )
        
        # 2. Grafikni natijalar matni bilan yuboramiz
        if chart_path and os.path.exists(chart_path):
            await message.answer_photo(
                FSInputFile(chart_path),
                caption=matn,
                parse_mode="HTML"
            )
        else:
            await message.answer(matn, parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {e}")
    finally:
        # Fayllarni tozalash
        if cert_path and os.path.exists(cert_path):
            os.remove(cert_path)
        if chart_path and os.path.exists(chart_path):
            os.remove(chart_path)

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

@router.message(F.text == "🏆 Mening o'rnim")
async def ranking_menu(message: Message):
    from admin import is_admin_id
    if is_admin_id(message.from_user.id):
        return
    ranking_enabled = get_setting('ranking_enabled', 'True')
    if ranking_enabled == 'False':
        # Agar o'chirilgan bo'lsa, menyuni yangilab qo'yamiz
        stats_enabled = get_setting('stats_enabled', 'True')
        await message.answer("⚠️ Reyting tizimi vaqtincha o'chirib qo'yilgan.", reply_markup=user_menu_keyboard(ranking_enabled, stats_enabled))
        return
    
    # Talabani user_id orqali topish
    from database import get_connection, release_connection
    import psycopg2.extras
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM talabalar WHERE user_id = %s", (message.from_user.id,))
    talaba = cur.fetchone()
    cur.close()
    release_connection(conn)

    if not talaba:
        await message.answer("⚠️ Avval profilingizni ulashing (Masalan: <code>ULASH_A-001</code>)", parse_mode="HTML")
        return

    ranks = get_student_rank(talaba['kod'])
    last_results = talaba_natijalari(talaba['kod'], limit=1)
    score = last_results[0]['umumiy_ball'] if last_results else 0
    
    text = (
        f"👤 <b>Sizning o'rningiz:</b>\n\n"
        f"🏫 Sinfda: <b>{ranks['class']}-o'rin</b>\n"
        f"🌍 Umumiy: <b>{ranks['overall']}-o'rin</b>\n\n"
        f"📈 Oxirgi ball: <b>{score}</b>\n\n"
        f"<i>Barcha sinflar orasidagi Top 50 talikni ko'rish uchun quyidagi tugmani bosing:</i>"
    )
    
    # Xabar turiga qarab (Message yoki CallbackQuery.message)
    if hasattr(message, 'edit_text'):
        await message.edit_text(text, parse_mode="HTML", reply_markup=ranking_keyboard(is_admin=False))
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=ranking_keyboard(is_admin=False))

@router.callback_query(F.data.startswith("ranking:"))
async def ranking_process(callback: CallbackQuery):
    action = callback.data.split(":")[1]
    
    # Admin tekshiruvi
    from admin import is_admin_id
    is_admin = is_admin_id(callback.from_user.id)
    
    # Talabani user_id orqali topish
    from database import get_connection, release_connection
    import psycopg2.extras
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM talabalar WHERE user_id = %s", (callback.from_user.id,))
    talaba = cur.fetchone()
    cur.close()
    release_connection(conn)

    if action == "overall_top50":
        if not is_admin and not check_access(callback.from_user.id):
            # Ruxsat yo'q bo'lsa, so'rov yuborish tugmasini ko'rsatish
            req = get_request_by_user(callback.from_user.id)
            if req and req['status'] == 'pending':
                await callback.answer("⏳ So'rovingiz ko'rib chiqilmoqda. Admin javobini kuting.", show_alert=True)
                return
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🙋‍♂️ Ruxsat so'rash", callback_data=f"request_access:{talaba['kod']}")],
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="ranking:back")]
            ])
            await callback.message.edit_text(
                "🔒 <b>Umumiy Top ro'yxatini ko'rish uchun admin ruxsati kerak.</b>\n\n"
                "Ruxsat so'rash uchun quyidagi tugmani bosing:",
                parse_mode="HTML",
                reply_markup=kb
            )
            return
        
        # Parallel sinflarni aniqlash (masalan: 11-A -> 11)
        sinf_prefix = None
        if talaba and talaba['sinf']:
            match = re.match(r'(\d+)', talaba['sinf'])
            if match:
                sinf_prefix = match.group(1)
        
        top50 = get_overall_ranking(sinf_prefix=sinf_prefix)
        if not top50:
            await callback.answer("⚠️ Hozircha natijalar yo'q.", show_alert=True)
            return
        
        header = f"🌍 <b>{sinf_prefix}-sinflar orasidagi Top 50:</b>\n\n" if sinf_prefix else "🌍 <b>Umumiy Top 50 o'quvchilar:</b>\n\n"
        text = header
        for i, t in enumerate(top50, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{emoji} {t['ismlar']} ({t['sinf']}) — <b>{t['umumiy_ball']}</b> ball\n"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=ranking_keyboard(is_admin=False))

    elif action == "back":
        await ranking_menu(callback.message)
    
    await callback.answer()

@router.callback_query(F.data.startswith("request_access:"))
async def request_access_process(callback: CallbackQuery):
    kod = callback.data.split(":")[1]
    add_access_request(callback.from_user.id, kod)
    
    # Talaba ma'lumotlarini olish
    talaba = talaba_topish(kod)
    
    # Adminlarga bildirishnoma yuborish
    from config import ADMIN_IDS
    from keyboards import request_actions_keyboard
    
    # request_id ni olish uchun oxirgi so'rovni olamiz
    req = get_request_by_user(callback.from_user.id)
    
    admin_text = (
        f"🔔 <b>Yangi kirish so'rovi!</b>\n\n"
        f"👤 O'quvchi: <b>{talaba['ismlar']}</b>\n"
        f"🏫 Sinf: <b>{talaba['sinf']}</b>\n"
        f"🎯 Yo'nalish: <b>{talaba['yonalish']}</b>\n"
        f"🆔 Kod: <code>{talaba['kod']}</code>\n"
        f"👤 Telegram ID: <code>{callback.from_user.id}</code>"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id, 
                admin_text, 
                parse_mode="HTML", 
                reply_markup=request_actions_keyboard(req['id'], callback.from_user.id)
            )
        except Exception:
            continue

    await callback.answer("✅ So'rov yuborildi. Admin tasdiqlashini kuting.", show_alert=True)
    await callback.message.edit_text("⏳ <b>So'rovingiz yuborildi.</b>\n\nAdmin tasdiqlaganidan keyin sizga xabar yuboramiz.", parse_mode="HTML")

# ─────────────────────────────────────────
# Statistika
# ─────────────────────────────────────────

@router.message(F.text == "📈 Statistika")
async def stats_menu(message: Message):
    stats_enabled = get_setting('stats_enabled', 'True')
    if stats_enabled == 'False':
        ranking_enabled = get_setting('ranking_enabled', 'True')
        await message.answer("⚠️ Statistika bo'limi vaqtincha o'chirib qo'yilgan.", reply_markup=user_menu_keyboard(ranking_enabled, stats_enabled))
        return
    await message.answer("📈 <b>Statistika bo'limi:</b>\n\nQuyidagilardan birini tanlang:", parse_mode="HTML", reply_markup=stats_keyboard())

@router.callback_query(F.data.startswith("stats:"))
async def stats_process(callback: CallbackQuery):
    action = callback.data.split(":")[1]
    
    if action == "direction":
        stats = get_avg_score_by_direction()
        if not stats:
            await callback.answer("⚠️ Ma'lumotlar yo'q.", show_alert=True)
            return
        
        # Grafik yaratish
        labels = [s['yonalish'][:15] + "..." if len(s['yonalish']) > 15 else s['yonalish'] for s in stats]
        values = [s['avg_score'] for s in stats]
        
        plt.figure(figsize=(10, 6))
        plt.bar(labels, values, color='skyblue')
        plt.title("Yo'nalishlar bo'yicha o'rtacha ballar")
        plt.ylabel("O'rtacha ball")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        path = "stats_direction.png"
        plt.savefig(path)
        plt.close()
        
        text = "🎯 <b>Yo'nalishlar bo'yicha o'rtacha ballar:</b>\n\n"
        for s in stats:
            text += f"• {s['yonalish']}: <b>{s['avg_score']}</b>\n"
        
        await callback.message.answer_photo(FSInputFile(path), caption=text, parse_mode="HTML")
        if os.path.exists(path): os.remove(path)
        await callback.message.delete()
        
    elif action == "class":
        stats = get_class_comparison()
        if not stats:
            await callback.answer("⚠️ Ma'lumotlar yo'q.", show_alert=True)
            return
            
        # Grafik yaratish
        labels = [s['sinf'] for s in stats]
        values = [s['avg_score'] for s in stats]
        
        plt.figure(figsize=(10, 6))
        plt.bar(labels, values, color='lightgreen')
        plt.title("Sinflar bo'yicha o'rtacha ballar")
        plt.ylabel("O'rtacha ball")
        plt.tight_layout()
        
        path = "stats_class.png"
        plt.savefig(path)
        plt.close()
        
        text = "🏫 <b>Sinflar bo'yicha o'rtacha ballar:</b>\n\n"
        for s in stats:
            text += f"• {s['sinf']}: <b>{s['avg_score']}</b>\n"
            
        await callback.message.answer_photo(FSInputFile(path), caption=text, parse_mode="HTML")
        if os.path.exists(path): os.remove(path)
        await callback.message.delete()
        
    elif action == "improved":
        students = get_most_improved_students()
        if not students:
            await callback.answer("⚠️ Ma'lumotlar yo'q.", show_alert=True)
            return
        text = "🚀 <b>Eng ko'p o'sishga erishganlar (oxirgi 2 test):</b>\n\n"
        for s in students:
            text += f"• {s['ismlar']} ({s['sinf']}): <b>+{s['diff']}</b> ball\n"
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=stats_keyboard())

    await callback.answer()

# ─────────────────────────────────────────
# Profil ma'lumotlari
# ─────────────────────────────────────────

@router.message(F.text == "📊 Mening natijalarim")
async def my_results(message: Message, state: FSMContext):
    # Foydalanuvchini user_id orqali topish
    from database import get_connection, release_connection
    import psycopg2.extras
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM talabalar WHERE user_id = %s", (message.from_user.id,))
    talaba = cur.fetchone()
    cur.close()
    release_connection(conn)

    await state.set_state(ResultCheckState.kod_kutish)
    await message.answer(
        "📝 <b>Natijangizni ko'rish uchun shaxsiy kodingizni yuboring:</b>",
        parse_mode="HTML"
    )

@router.message(ResultCheckState.kod_kutish)
async def process_result_code(message: Message, state: FSMContext):
    if message.text in ADMIN_TUGMALAR:
        await state.clear()
        return

    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    
    if not talaba:
        await message.answer("❌ Bunday kod topilmadi. Iltimos, qaytadan urinib ko'ring.")
        await state.set_state(ResultCheckState.kod_kutish)
        return

    await state.clear()
    await send_full_results(message, kod)

# ─────────────────────────────────────────
# Shaxsiy kabinet va Inline rejim
# ─────────────────────────────────────────

@router.message(F.text == "👤 Shaxsiy kabinet")
async def student_profile(message: Message):
    from database import get_connection, release_connection
    import psycopg2.extras
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM talabalar WHERE user_id = %s", (message.from_user.id,))
    talaba = cur.fetchone()
    cur.close()
    release_connection(conn)

    if not talaba:
        await message.answer("⚠️ Avval profilingizni ulashing (Masalan: ULASH_A-001)")
        return

    natijalar = talaba_natijalari(talaba['kod'], limit=5)
    oxirgi_ball = natijalar[0]['umumiy_ball'] if natijalar else 0
    jami_test = len(talaba_natijalari(talaba['kod'], limit=1000))
    
    text = (
        f"👤 <b>Shaxsiy kabinet</b>\n\n"
        f"🆔 Kod: <code>{talaba['kod']}</code>\n"
        f"👤 Ism: <b>{talaba['ismlar']}</b>\n"
        f"🏫 Sinf: <b>{talaba['sinf']}</b>\n"
        f"🎯 Yo'nalish: <b>{talaba['yonalish']}</b>\n\n"
        f"📊 Statistika:\n"
        f"✅ Jami topshirilgan testlar: <b>{jami_test} ta</b>\n"
        f"📈 Oxirgi natija: <b>{oxirgi_ball} ball</b>\n"
    )
    
    await message.answer(text, parse_mode="HTML", reply_markup=profile_keyboard())

@router.callback_query(F.data.startswith("profile:"))
async def profile_callback(callback: CallbackQuery):
    action = callback.data.split(":")[1]
    
    from database import get_connection, release_connection
    import psycopg2.extras
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM talabalar WHERE user_id = %s", (callback.from_user.id,))
    talaba = cur.fetchone()
    cur.close()
    release_connection(conn)

    if not talaba:
        await callback.answer("⚠️ Xato: Talaba topilmadi.", show_alert=True)
        return

    if action == "history":
        history = talaba_natijalari(talaba['kod'], limit=10)
        if not history:
            await callback.answer("📜 Hozircha testlar tarixi mavjud emas.", show_alert=True)
            return
        
        text = f"📜 <b>Oxirgi 10 ta test natijalari:</b>\n\n"
        for i, res in enumerate(history, 1):
            sana = res['test_sanasi'].strftime("%d.%m.%Y")
            text += f"{i}. {sana} — <b>{res['umumiy_ball']} ball</b>\n"
        
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=profile_keyboard())
    
    elif action == "refresh":
        await callback.message.delete()
        await student_profile(callback.message)
    
    await callback.answer()

@router.inline_query(F.query == "my_result")
async def inline_result_handler(inline_query: InlineQuery):
    from database import get_connection, release_connection
    import psycopg2.extras
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM talabalar WHERE user_id = %s", (inline_query.from_user.id,))
    talaba = cur.fetchone()
    cur.close()
    release_connection(conn)

    if not talaba:
        return

    res = talaba_songi_natija(talaba['kod'])
    if not res:
        return

    text = (
        f"📊 <b>Mening test natijam!</b>\n\n"
        f"👤 O'quvchi: <b>{talaba['ismlar']}</b>\n"
        f"🏫 Sinf: <b>{talaba['sinf']}</b>\n"
        f"📈 Umumiy ball: <b>{res['umumiy_ball']}</b>\n"
        f"📅 Sana: <b>{res['test_sanasi'].strftime('%d.%m.%Y')}</b>\n\n"
        f"🤖 @{(await inline_query.bot.get_me()).username}"
    )

    results = [
        InlineQueryResultArticle(
            id="my_res",
            title="Mening natijamni ulashish",
            description=f"Oxirgi ball: {res['umumiy_ball']}",
            input_message_content=InputTextMessageContent(message_text=text, parse_mode="HTML")
        )
    ]
    await inline_query.answer(results, is_personal=True, cache_time=5)
