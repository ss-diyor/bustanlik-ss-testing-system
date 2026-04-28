"""
Ota-ona portali moduli — To'liq panel.

Xususiyatlar:
    ✅ Bir nechta farzandni kuzatish (max 10 ta)
    ✅ Har bir farzand uchun natija va reyting
    ✅ Yangi natija kelganda avtomatik xabarnoma
    ✅ Farzand qo'shish / o'chirish
    ✅ Admin bilan bog'lanish
    ✅ Qulay reply keyboard paneli

Foydalanish:
    "PARENT_A007" → farzand ulanadi va panel ochiladi.
"""

import logging
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import (
    talaba_topish,
    talaba_natijalari,
    talaba_songi_natija,
    get_student_rank,
    get_connection,
    release_connection,
)
from keyboards import (
    ota_ona_menu_keyboard,
    farzandlar_tanlash_keyboard,
    farzandlar_boshqarish_keyboard,
    farzand_natija_keyboard,
    murojaat_javob_keyboard,
    murojaat_bekor_qilish_keyboard,
)

router = Router()
logger = logging.getLogger(__name__)

MAX_FARZAND = 10  # Bir ota-ona maksimal qo'sha oladigan farzand soni


# ─── FSM holatlari ─────────────────────────────────────────────────────────────

class ParentStates(StatesGroup):
    kod_kutish = State()       # Yangi farzand kodi kutilmoqda
    murojaat_kutish = State()  # Admin bilan bog'lanish xabari


# ─── Ma'lumotlar bazasi funksiyalari ──────────────────────────────────────────

def _ensure_table(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ota_ona_bog (
            id SERIAL PRIMARY KEY,
            parent_user_id BIGINT NOT NULL,
            talaba_kod VARCHAR(20) NOT NULL,
            bog_vaqti TIMESTAMP DEFAULT NOW(),
            UNIQUE (parent_user_id, talaba_kod)
        )
    """)


def parent_qosh(parent_user_id: int, talaba_kod: str) -> str:
    """
    Ota-onani talabaga ulaydi.
    Qaytaradi:
        'ok'       — muvaffaqiyatli ulandi
        'exists'   — allaqachon mavjud
        'limit'    — limit to'lib ketgan
        'error'    — xato
    """
    try:
        conn = get_connection()
        cur = conn.cursor()
        _ensure_table(cur)

        cur.execute(
            "SELECT COUNT(*) FROM ota_ona_bog WHERE parent_user_id = %s",
            (parent_user_id,)
        )
        count = cur.fetchone()[0]

        # Allaqachon ulangan tekshirish
        cur.execute(
            "SELECT 1 FROM ota_ona_bog WHERE parent_user_id = %s AND talaba_kod = %s",
            (parent_user_id, talaba_kod.upper())
        )
        if cur.fetchone():
            cur.close()
            release_connection(conn)
            return "exists"

        if count >= MAX_FARZAND:
            cur.close()
            release_connection(conn)
            return "limit"

        cur.execute(
            "INSERT INTO ota_ona_bog (parent_user_id, talaba_kod) VALUES (%s, %s)",
            (parent_user_id, talaba_kod.upper())
        )
        conn.commit()
        cur.close()
        release_connection(conn)
        return "ok"
    except Exception as e:
        logger.error(f"parent_qosh xato: {e}")
        return "error"


def parent_farzandlar(parent_user_id: int) -> list:
    """Ota-onaga ulangan barcha farzandlar kodini qaytaradi."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        _ensure_table(cur)
        cur.execute(
            "SELECT talaba_kod FROM ota_ona_bog WHERE parent_user_id = %s ORDER BY bog_vaqti",
            (parent_user_id,)
        )
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return [r[0] for r in rows]
    except Exception as e:
        logger.error(f"parent_farzandlar xato: {e}")
        return []


def parent_bog_ochir(parent_user_id: int, talaba_kod: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM ota_ona_bog WHERE parent_user_id = %s AND talaba_kod = %s",
            (parent_user_id, talaba_kod.upper())
        )
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception as e:
        logger.error(f"parent_bog_ochir xato: {e}")
        return False


def parent_ekanligini_tekshir(user_id: int) -> bool:
    return len(parent_farzandlar(user_id)) > 0


def talaba_barcha_ota_onalari(talaba_kod: str) -> list:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT parent_user_id FROM ota_ona_bog WHERE talaba_kod = %s",
            (talaba_kod.upper(),)
        )
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return [r[0] for r in rows]
    except Exception:
        return []


# ─── Yordamchi funksiyalar ────────────────────────────────────────────────────

def _ball_emoji(ball: float) -> str:
    if ball >= 160:
        return "🥇"
    elif ball >= 130:
        return "🥈"
    elif ball >= 100:
        return "🥉"
    return "📝"


def farzand_qisqa_kartochka(kod: str) -> str:
    talaba = talaba_topish(kod)
    if not talaba:
        return f"❓ <b>{kod}</b> — ma'lumot topilmadi"
    ism = talaba.get("ismlar", "Noma'lum")
    sinf = talaba.get("sinf", "—")
    yonalish = talaba.get("yonalish", "—")
    songi = talaba_songi_natija(kod)
    if songi:
        ball = float(songi.get("umumiy_ball", 0))
        natija_text = f"{_ball_emoji(ball)} So'nggi ball: <b>{ball:.1f}</b>"
    else:
        natija_text = "📭 Hali natija yo'q"
    return (
        f"👤 <b>{ism}</b>\n"
        f"   🏫 {sinf}  |  📚 {yonalish}\n"
        f"   {natija_text}"
    )


def farzand_batafsil_natija(kod: str) -> str:
    talaba = talaba_topish(kod)
    if not talaba:
        return f"❌ <b>{kod}</b> kodli o'quvchi topilmadi."
    ism = talaba.get("ismlar", "Noma'lum")
    sinf = talaba.get("sinf", "—")
    yonalish = talaba.get("yonalish", "—")
    rank = get_student_rank(kod)
    natijalar = talaba_natijalari(kod, limit=5)

    matn = (
        f"📋 <b>{ism}</b>\n"
        f"🏫 Sinf: <b>{sinf}</b>  |  📚 Yo'nalish: <b>{yonalish}</b>\n"
    )
    if rank:
        umumiy = rank.get("overall_rank") or rank.get("overall")
        sinf_rank = rank.get("class_rank") or rank.get("class")
        if sinf_rank:
            matn += f"📊 Sinf reytingi: <b>{sinf_rank}-o'rin</b>\n"
        if umumiy:
            matn += f"🏆 Umumiy reyting: <b>{umumiy}-o'rin</b>\n"
    matn += "\n"

    if not natijalar:
        matn += "📭 Hozircha test natijalari mavjud emas."
        return matn

    matn += f"📊 <b>So'nggi {min(len(natijalar), 5)} ta natija:</b>\n\n"
    for i, n in enumerate(natijalar[:5], 1):
        sana = str(n.get("test_sanasi", ""))[:10]
        ball = float(n.get("umumiy_ball", 0))
        maj = n.get("majburiy", 0)
        as1 = n.get("asosiy_1", 0)
        as2 = n.get("asosiy_2", 0)
        matn += (
            f"{_ball_emoji(ball)} <b>{i}-test</b> ({sana})\n"
            f"   Jami: <b>{ball:.1f}</b> | Majburiy: {maj} | "
            f"Asosiy-1: {as1} | Asosiy-2: {as2}\n\n"
        )
    return matn


# ─── Panel ko'rsatish ─────────────────────────────────────────────────────────

async def ota_ona_panel_korsatish(message: Message, farzandlar: list):
    soni = len(farzandlar)
    matn = f"👨‍👩‍👦 <b>Ota-ona paneli</b>\n\nUlangan farzandlar: <b>{soni} ta</b>\n\n"
    for kod in farzandlar:
        matn += farzand_qisqa_kartochka(kod) + "\n\n"
    matn += "📌 Quyidagi tugmalardan foydalaning:"
    await message.answer(matn, parse_mode="HTML", reply_markup=ota_ona_menu_keyboard())


# ─── PARENT_ kodi orqali ulash ────────────────────────────────────────────────

@router.message(F.text.startswith("PARENT_"))
async def ota_ona_ulash(message: Message):
    kod = message.text.replace("PARENT_", "").strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer(
            "❌ <b>O'quvchi topilmadi.</b>\n\n"
            "Farzandingizning to'g'ri shaxsiy kodini kiriting.\n"
            "Masalan: <code>PARENT_A007</code>",
            parse_mode="HTML"
        )
        return

    result = parent_qosh(message.from_user.id, kod)
    farzandlar = parent_farzandlar(message.from_user.id)

    if result == "ok":
        await message.answer(
            f"✅ <b>{talaba.get('ismlar')}</b> muvaffaqiyatli ulandi!\n\n"
            f"Bundan buyon yangi natijalar haqida avtomatik xabar olasiz. 🔔",
            parse_mode="HTML"
        )
    elif result == "exists":
        await message.answer(
            f"ℹ️ <b>{talaba.get('ismlar')}</b> allaqachon ro'yxatingizda mavjud.",
            parse_mode="HTML"
        )
    elif result == "limit":
        await message.answer(
            f"⚠️ Siz maksimal <b>{MAX_FARZAND} ta</b> farzand qo'sha olasiz.",
            parse_mode="HTML"
        )

    await ota_ona_panel_korsatish(message, farzandlar)


# ─── Farzandlarim tugmasi ─────────────────────────────────────────────────────

@router.message(F.text == "👨‍👩‍👦 Farzandlarim")
async def farzandlar_royxati(message: Message):
    farzandlar = parent_farzandlar(message.from_user.id)
    if not farzandlar:
        await message.answer(
            "📭 <b>Hozircha ulangan farzandlar yo'q.</b>\n\n"
            "<b>➕ Farzand qo'shish</b> tugmasini bosing\n"
            "yoki <code>PARENT_KOD</code> deb yozing.",
            parse_mode="HTML"
        )
        return

    matn = f"👨‍👩‍👦 <b>Farzandlaringiz ro'yxati</b> ({len(farzandlar)} ta):\n\n"
    for i, kod in enumerate(farzandlar, 1):
        t = talaba_topish(kod)
        if t:
            matn += f"{i}. <b>{t.get('ismlar', kod)}</b> — {t.get('sinf', '—')}\n"
        else:
            matn += f"{i}. <b>{kod}</b>\n"
    matn += "\nBatafsil yoki o'chirish uchun tanlang:"
    await message.answer(
        matn, parse_mode="HTML",
        reply_markup=farzandlar_boshqarish_keyboard(farzandlar)
    )


# ─── Farzand qo'shish ─────────────────────────────────────────────────────────

@router.message(F.text == "➕ Farzand qo'shish")
async def farzand_qoshish_start(message: Message, state: FSMContext):
    farzandlar = parent_farzandlar(message.from_user.id)
    if len(farzandlar) >= MAX_FARZAND:
        await message.answer(
            f"⚠️ Maksimal <b>{MAX_FARZAND} ta</b> farzand qo'sha olasiz.\n"
            "Avval birini o'chirib, keyin yangisini qo'shing.",
            parse_mode="HTML"
        )
        return
    await state.set_state(ParentStates.kod_kutish)
    await message.answer(
        "📝 <b>Farzandingizning shaxsiy kodini kiriting:</b>\n\n"
        "Masalan: <code>A007</code> yoki <code>52B</code>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(ParentStates.kod_kutish)
async def farzand_kodi_qabul(message: Message, state: FSMContext):
    await state.clear()
    kod = message.text.strip().upper() if message.text else ""
    if not kod:
        await message.answer("❌ Kod kiritilmadi.")
        farzandlar = parent_farzandlar(message.from_user.id)
        await ota_ona_panel_korsatish(message, farzandlar)
        return

    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer(
            f"❌ <b>{kod}</b> kodli o'quvchi topilmadi.",
            parse_mode="HTML"
        )
        farzandlar = parent_farzandlar(message.from_user.id)
        await ota_ona_panel_korsatish(message, farzandlar)
        return

    result = parent_qosh(message.from_user.id, kod)
    farzandlar = parent_farzandlar(message.from_user.id)

    if result == "ok":
        await message.answer(
            f"✅ <b>{talaba.get('ismlar')}</b> ({talaba.get('sinf', '—')}) qo'shildi! 🎉",
            parse_mode="HTML"
        )
    elif result == "exists":
        await message.answer(
            f"ℹ️ <b>{talaba.get('ismlar')}</b> allaqachon ro'yxatda mavjud.",
            parse_mode="HTML"
        )
    elif result == "limit":
        await message.answer(
            f"⚠️ Maksimal limit: <b>{MAX_FARZAND} ta</b>.", parse_mode="HTML"
        )

    await ota_ona_panel_korsatish(message, farzandlar)


# ─── Farzandim natijasi ───────────────────────────────────────────────────────

@router.message(F.text == "📊 Farzandim natijasi")
async def farzand_natija_tanlash(message: Message):
    farzandlar = parent_farzandlar(message.from_user.id)
    if not farzandlar:
        await message.answer(
            "📭 Hech qanday farzand ulanmagan.\n"
            "<b>➕ Farzand qo'shish</b> tugmasini bosing.",
            parse_mode="HTML"
        )
        return
    if len(farzandlar) == 1:
        matn = farzand_batafsil_natija(farzandlar[0])
        await message.answer(matn, parse_mode="HTML",
                             reply_markup=farzand_natija_keyboard(farzandlar[0]))
    else:
        await message.answer(
            f"👇 <b>Qaysi farzandingizning natijasini ko'rmoqchisiz?</b>\n"
            f"(Jami: {len(farzandlar)} ta farzand)",
            parse_mode="HTML",
            reply_markup=farzandlar_tanlash_keyboard(farzandlar)
        )


# ─── Farzandim reytingi ───────────────────────────────────────────────────────

@router.message(F.text == "🏆 Farzandim reytingi")
async def farzand_reyting_tanlash(message: Message):
    farzandlar = parent_farzandlar(message.from_user.id)
    if not farzandlar:
        await message.answer("📭 Hech qanday farzand ulanmagan.")
        return
    if len(farzandlar) == 1:
        await _reyting_matn_yuborish(message, farzandlar[0])
    else:
        buttons = []
        for k in farzandlar:
            t = talaba_topish(k)
            label = f"👤 {t.get('ismlar', k)}" if t else f"👤 {k}"
            buttons.append([InlineKeyboardButton(text=label, callback_data=f"parent_rank:{k}")])
        await message.answer(
            "🏆 <b>Qaysi farzandingizning reytingini ko'rmoqchisiz?</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )


async def _reyting_matn_yuborish(message: Message, kod: str):
    talaba = talaba_topish(kod)
    ism = talaba.get("ismlar", kod) if talaba else kod
    sinf = talaba.get("sinf", "—") if talaba else "—"
    rank = get_student_rank(kod)
    matn = f"🏆 <b>{ism}</b> ({sinf}) reytingi\n\n"
    if not rank:
        matn += "📭 Reyting ma'lumotlari mavjud emas."
    else:
        sinf_rank = rank.get("class_rank") or rank.get("class")
        umumiy = rank.get("overall_rank") or rank.get("overall")
        if sinf_rank:
            matn += f"📊 Sinf ichida: <b>{sinf_rank}-o'rin</b>\n"
        if umumiy:
            matn += f"🌐 Umumiy: <b>{umumiy}-o'rin</b>\n"
        songi = talaba_songi_natija(kod)
        if songi:
            matn += f"\n🎯 So'nggi ball: <b>{float(songi.get('umumiy_ball', 0)):.1f}</b>"
    await message.answer(matn, parse_mode="HTML")


# ─── Admin bilan bog'lanish ───────────────────────────────────────────────────

@router.message(F.text == "✍️ Admin bilan bog'lanish")
async def ota_ona_murojaat_start(message: Message, state: FSMContext):
    await state.set_state(ParentStates.murojaat_kutish)
    await message.answer(
        "✍️ <b>Xabaringizni yozing:</b>\n\nAdmin imkon topishi bilan javob beradi.",
        parse_mode="HTML",
        reply_markup=murojaat_bekor_qilish_keyboard()
    )


@router.message(ParentStates.murojaat_kutish)
async def ota_ona_murojaat_yuborish(message: Message, state: FSMContext):
    from config import ADMIN_IDS
    farzandlar = parent_farzandlar(message.from_user.id)

    if message.text == "вќЊ Bekor qilish":
        await state.clear()
        await message.answer(
            "вќЊ Xabar yuborish bekor qilindi.",
            reply_markup=ota_ona_menu_keyboard(),
        )
        return

    await state.clear()

    farzand_text = ""
    for kod in farzandlar[:3]:
        t = talaba_topish(kod)
        if t:
            farzand_text += f"\n  • {t.get('ismlar', kod)} ({t.get('sinf', '')})"

    user = message.from_user
    murojaat = (
        f"📩 <b>Ota-ona murojaati!</b>\n\n"
        f"👤 Kim: {user.full_name}"
        f"{f' (@{user.username})' if user.username else ''}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"👨‍👩‍👦 Farzandlari:{farzand_text or ' — (ulanmagan)'}\n\n"
        f"💬 Xabar:\n{message.text}"
    )

    yuborildi = 0
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id, murojaat, parse_mode="HTML",
                reply_markup=murojaat_javob_keyboard(message.from_user.id)
            )
            yuborildi += 1
        except Exception as e:
            logger.warning(f"Admin {admin_id} ga yuborib bo'lmadi: {e}")

    await message.answer(
        "✅ <b>Xabaringiz adminlarga yuborildi!</b>" if yuborildi > 0
        else "⚠️ Xabar yuborishda muammo yuz berdi.",
        parse_mode="HTML"
    )
    await ota_ona_panel_korsatish(message, farzandlar)


# ─── Chiqish ──────────────────────────────────────────────────────────────────

@router.message(F.text == "🚪 Chiqish (Ota-ona)")
async def ota_ona_chiqish(message: Message):
    from keyboards import user_menu_keyboard
    from database import get_setting
    ranking_enabled = get_setting("ranking_enabled", "True")
    stats_enabled = get_setting("stats_enabled", "True")
    chatbot_enabled = get_setting("chatbot_enabled", "True")
    mock_enabled = get_setting("mock_enabled", "True")
    await message.answer(
        "🚪 Ota-ona panelidan chiqdingiz.\n\n"
        "Qayta kirish: <code>PARENT_KOD</code> deb yozing.",
        parse_mode="HTML",
        reply_markup=user_menu_keyboard(ranking_enabled, stats_enabled, chatbot_enabled, mock_enabled)
    )


# ─── Inline callbacklar ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("parent_select:"))
async def farzand_select_natija(callback: CallbackQuery):
    kod = callback.data.split(":")[1]
    matn = farzand_batafsil_natija(kod)
    await callback.message.edit_text(matn, parse_mode="HTML",
                                     reply_markup=farzand_natija_keyboard(kod))
    await callback.answer()


@router.callback_query(F.data.startswith("parent_view:"))
async def farzand_view_callback(callback: CallbackQuery):
    kod = callback.data.split(":")[1]
    matn = farzand_batafsil_natija(kod)
    await callback.message.edit_text(
        matn, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Barcha natijalar",
                                  callback_data=f"parent_all_results:{kod}")],
            [InlineKeyboardButton(text="🏆 Reytingi",
                                  callback_data=f"parent_rank:{kod}")],
            [InlineKeyboardButton(text="◀️ Orqaga",
                                  callback_data="parent_back_list")],
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("parent_all_results:"))
async def farzand_all_results(callback: CallbackQuery):
    kod = callback.data.split(":")[1]
    talaba = talaba_topish(kod)
    natijalar = talaba_natijalari(kod, limit=10)
    ism = talaba.get("ismlar", kod) if talaba else kod
    matn = f"📋 <b>{ism}</b> — barcha natijalar\n\n"
    if not natijalar:
        matn += "📭 Hozircha natijalar yo'q."
    else:
        for i, n in enumerate(natijalar, 1):
            sana = str(n.get("test_sanasi", ""))[:10]
            ball = float(n.get("umumiy_ball", 0))
            matn += f"{_ball_emoji(ball)} <b>{i}.</b> {sana} — <b>{ball:.1f}</b> ball\n"
    await callback.message.edit_text(
        matn, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga",
                                  callback_data=f"parent_view:{kod}")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("parent_rank:"))
async def farzand_rank_callback(callback: CallbackQuery):
    kod = callback.data.split(":")[1]
    talaba = talaba_topish(kod)
    ism = talaba.get("ismlar", kod) if talaba else kod
    sinf = talaba.get("sinf", "—") if talaba else "—"
    rank = get_student_rank(kod)
    matn = f"🏆 <b>{ism}</b> ({sinf}) reytingi\n\n"
    if not rank:
        matn += "📭 Reyting ma'lumotlari yo'q."
    else:
        sinf_rank = rank.get("class_rank") or rank.get("class")
        umumiy = rank.get("overall_rank") or rank.get("overall")
        if sinf_rank:
            matn += f"📊 Sinf ichida: <b>{sinf_rank}-o'rin</b>\n"
        if umumiy:
            matn += f"🌐 Umumiy: <b>{umumiy}-o'rin</b>\n"
    await callback.message.edit_text(
        matn, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga",
                                  callback_data=f"parent_view:{kod}")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("parent_del:"))
async def farzand_del_callback(callback: CallbackQuery):
    kod = callback.data.split(":")[1]
    talaba = talaba_topish(kod)
    ism = talaba.get("ismlar", kod) if talaba else kod
    parent_bog_ochir(callback.from_user.id, kod)
    farzandlar = parent_farzandlar(callback.from_user.id)
    if not farzandlar:
        await callback.message.edit_text(
            f"✅ <b>{ism}</b> olib tashlandi.\n\n📭 Ro'yxat bo'sh.",
            parse_mode="HTML"
        )
    else:
        matn = f"✅ <b>{ism}</b> olib tashlandi.\n\nQolgan farzandlar ({len(farzandlar)} ta):"
        await callback.message.edit_text(
            matn, parse_mode="HTML",
            reply_markup=farzandlar_boshqarish_keyboard(farzandlar)
        )
    await callback.answer(f"✅ {ism} o'chirildi")


@router.callback_query(F.data == "parent_back_list")
async def parent_back_list_callback(callback: CallbackQuery):
    farzandlar = parent_farzandlar(callback.from_user.id)
    if not farzandlar:
        await callback.message.edit_text("📭 Farzandlar ro'yxati bo'sh.", parse_mode="HTML")
    else:
        await callback.message.edit_text(
            f"👨‍👩‍👦 <b>Farzandlaringiz</b> ({len(farzandlar)} ta):",
            parse_mode="HTML",
            reply_markup=farzandlar_boshqarish_keyboard(farzandlar)
        )
    await callback.answer()


@router.callback_query(F.data == "parent_add_inline")
async def parent_add_inline_callback(callback: CallbackQuery, state: FSMContext):
    farzandlar = parent_farzandlar(callback.from_user.id)
    if len(farzandlar) >= MAX_FARZAND:
        await callback.answer(
            f"⚠️ Maksimal {MAX_FARZAND} ta farzand qo'sha olasiz!", show_alert=True
        )
        return
    await state.set_state(ParentStates.kod_kutish)
    await callback.message.answer(
        "📝 <b>Farzandingizning shaxsiy kodini kiriting:</b>\n\nMasalan: <code>A007</code>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    await callback.answer()


# ─── Yangi natija → ota-onalarga avtomatik xabarnoma ─────────────────────────

async def ota_onalarga_xabar_yuborish(bot, talaba_kod: str, yangi_ball: float):
    """admin.py dan chaqiriladi — yangi natija kiritilganda."""
    from database import is_notification_enabled

    ota_onalar = talaba_barcha_ota_onalari(talaba_kod)
    if not ota_onalar:
        return
    talaba = talaba_topish(talaba_kod)
    if not talaba:
        return
    ism = talaba.get("ismlar", talaba_kod)
    sinf = talaba.get("sinf", "—")
    em = _ball_emoji(yangi_ball)
    xabar = (
        f"🔔 <b>Yangi natija!</b>\n\n"
        f"👤 Farzandingiz: <b>{ism}</b> ({sinf})\n"
        f"🎯 Ball: <b>{yangi_ball:.1f}</b> {em}\n\n"
        f"📊 Ko'rish: <b>📊 Farzandim natijasi</b> tugmasini bosing."
    )
    for parent_id in ota_onalar:
        if not is_notification_enabled(parent_id, "notify_results"):
            continue
        try:
            await bot.send_message(parent_id, xabar, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Ota-onaga xabar yuborib bo'lmadi (id={parent_id}): {e}")

