"""
Ota-ona portali moduli.

Ota-onalar o'z farzandlarining DTM natijalarini alohida
"PARENT_KODINGIZ" buyrug'i orqali kuzatib borishi mumkin.

Foydalanish:
    Botga "PARENT_A007" deb yozilsa, A007 kodli talabaning
    so'nggi natijalari va reytingi ko'rsatiladi.
    Har safar yangi natija qo'shilganda ota-onaga ham
    avtomatik xabar yuboriladi (agar ulangan bo'lsa).
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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

router = Router()
logger = logging.getLogger(__name__)


# ─── FSM holatlari ─────────────────────────────────────────────────────────────

class ParentStates(StatesGroup):
    kod_kutish = State()


# ─── Ma'lumotlar bazasi yordamchi funksiyalari ─────────────────────────────────

def parent_qosh(parent_user_id: int, talaba_kod: str) -> bool:
    """Ota-onani talabaga ulaydi (bir ota-ona bir nechta farzandni kuzatishi mumkin)."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ota_ona_bog (
                id SERIAL PRIMARY KEY,
                parent_user_id BIGINT NOT NULL,
                talaba_kod VARCHAR(20) NOT NULL,
                bog_vaqti TIMESTAMP DEFAULT NOW(),
                UNIQUE (parent_user_id, talaba_kod)
            )
        """)
        cur.execute("""
            INSERT INTO ota_ona_bog (parent_user_id, talaba_kod)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, (parent_user_id, talaba_kod.upper()))
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception as e:
        logger.error(f"parent_qosh xato: {e}")
        return False


def parent_farzandlar(parent_user_id: int) -> list:
    """Ota-onaga ulangan barcha farzandlar kodini qaytaradi."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ota_ona_bog (
                id SERIAL PRIMARY KEY,
                parent_user_id BIGINT NOT NULL,
                talaba_kod VARCHAR(20) NOT NULL,
                bog_vaqti TIMESTAMP DEFAULT NOW(),
                UNIQUE (parent_user_id, talaba_kod)
            )
        """)
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
    """Ota-ona va talaba o'rtasidagi bog'lanishni o'chiradi."""
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


def talaba_barcha_ota_onalari(talaba_kod: str) -> list[int]:
    """Berilgan talabaga ulangan barcha ota-onalarning user_id larini qaytaradi."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT parent_user_id FROM ota_ona_bog WHERE talaba_kod = %s
        """, (talaba_kod.upper(),))
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return [r[0] for r in rows]
    except Exception:
        return []


# ─── Natija matni yasash ───────────────────────────────────────────────────────

def natija_matn_yasash(talaba: dict, natijalar: list, rank_info: dict | None) -> str:
    """Ota-ona uchun o'qilishi qulay natija matni."""
    ism = talaba.get("ismlar", "Noma'lum")
    sinf = talaba.get("sinf", "—")
    yonalish = talaba.get("yonalish", "—")

    matn = (
        f"👨‍👩‍👦 <b>Farzandingiz: {ism}</b>\n"
        f"🏫 Sinf: {sinf}  |  📚 Yo'nalish: {yonalish}\n"
    )

    if rank_info:
        umumiy = rank_info.get("overall_rank")
        sinf_rank = rank_info.get("class_rank")
        if umumiy:
            matn += f"🏆 Umumiy reyting: <b>{umumiy}-o'rin</b>\n"
        if sinf_rank:
            matn += f"📊 Sinf reytingi: <b>{sinf_rank}-o'rin</b>\n"

    matn += "\n"

    if not natijalar:
        matn += "ℹ️ Hozircha test natijalari mavjud emas."
        return matn

    matn += f"📋 <b>So'nggi {min(len(natijalar), 5)} ta natija:</b>\n\n"

    for i, n in enumerate(natijalar[:5], 1):
        sana = str(n.get("test_sanasi", ""))[:10]
        ball = n.get("umumiy_ball", 0)
        majburiy = n.get("majburiy", 0)
        asosiy_1 = n.get("asosiy_1", 0)
        asosiy_2 = n.get("asosiy_2", 0)

        # Dinamik emoji (ball bo'yicha)
        if ball >= 160:
            emoji = "🥇"
        elif ball >= 120:
            emoji = "🥈"
        elif ball >= 80:
            emoji = "🥉"
        else:
            emoji = "📝"

        matn += (
            f"{emoji} <b>{i}-test</b> ({sana})\n"
            f"   Jami ball: <b>{ball:.1f}</b>\n"
            f"   Majburiy: {majburiy}  |  Asosiy-1: {asosiy_1}  |  Asosiy-2: {asosiy_2}\n\n"
        )

    return matn


# ─── Farzand qo'shish/ko'rish tugmalari ──────────────────────────────────────

def farzandlar_keyboard(farzandlar: list) -> InlineKeyboardMarkup:
    buttons = []
    for kod in farzandlar:
        talaba = talaba_topish(kod)
        ism = talaba.get("ismlar", kod) if talaba else kod
        buttons.append([
            InlineKeyboardButton(text=f"👤 {ism} ({kod})", callback_data=f"parent_view:{kod}"),
            InlineKeyboardButton(text="❌", callback_data=f"parent_del:{kod}"),
        ])
    buttons.append([InlineKeyboardButton(text="➕ Yangi farzand qo'shish", callback_data="parent_add")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Handlerlar ───────────────────────────────────────────────────────────────

@router.message(F.text.startswith("PARENT_"))
async def ota_ona_ulash(message: Message):
    """PARENT_KODINGIZ buyrug'i orqali farzandni ulash."""
    kod = message.text.replace("PARENT_", "").strip().upper()
    talaba = talaba_topish(kod)

    if not talaba:
        await message.answer(
            "❌ <b>Talaba topilmadi.</b>\n\n"
            "Iltimos, farzandingizning shaxsiy kodini to'g'ri kiriting.\n"
            "Masalan: <code>PARENT_A007</code>",
            parse_mode="HTML"
        )
        return

    ok = parent_qosh(message.from_user.id, kod)
    if not ok:
        await message.answer("⚠️ Ulanishda xato yuz berdi. Iltimos qayta urinib ko'ring.")
        return

    natijalar = talaba_natijalari(kod, limit=5)
    rank_info = get_student_rank(kod)
    matn = natija_matn_yasash(talaba, natijalar, rank_info)

    await message.answer(
        f"✅ <b>Muvaffaqiyatli ulandi!</b>\n\n"
        f"Bundan buyon <b>{talaba.get('ismlar')}</b> uchun yangi natijalar haqida "
        f"sizga avtomatik xabar yuboriladi.\n\n"
        + matn,
        parse_mode="HTML"
    )


@router.message(F.text == "👨‍👩‍👦 Farzandlarim")
async def farzandlar_menu(message: Message):
    """Ota-ona menyu — ulanган farzandlar ro'yxati."""
    farzandlar = parent_farzandlar(message.from_user.id)

    if not farzandlar:
        await message.answer(
            "📭 <b>Hozircha ulangan farzandlar yo'q.</b>\n\n"
            "Farzandingizni ulash uchun:\n"
            "<code>PARENT_KODINGIZ</code> deb yozing.\n"
            "Masalan: <code>PARENT_A007</code>",
            parse_mode="HTML"
        )
        return

    await message.answer(
        "👨‍👩‍👦 <b>Farzandlaringiz ro'yxati:</b>\n\n"
        "Natijalarni ko'rish uchun ismni tanlang:",
        parse_mode="HTML",
        reply_markup=farzandlar_keyboard(farzandlar)
    )


@router.callback_query(F.data.startswith("parent_view:"))
async def farzand_natija_korish(callback: CallbackQuery):
    """Tanlangan farzandning natijalarini ko'rsatish."""
    kod = callback.data.split(":")[1]
    talaba = talaba_topish(kod)

    if not talaba:
        await callback.answer("❌ Talaba topilmadi.", show_alert=True)
        return

    natijalar = talaba_natijalari(kod, limit=5)
    rank_info = get_student_rank(kod)
    matn = natija_matn_yasash(talaba, natijalar, rank_info)

    await callback.message.edit_text(
        matn,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data="parent_back")]
        ])
    )
    await callback.answer()


@router.callback_query(F.data.startswith("parent_del:"))
async def farzand_bog_ochirish(callback: CallbackQuery):
    """Farzand bog'lanishini o'chirish."""
    kod = callback.data.split(":")[1]
    talaba = talaba_topish(kod)
    ism = talaba.get("ismlar", kod) if talaba else kod

    parent_bog_ochir(callback.from_user.id, kod)
    farzandlar = parent_farzandlar(callback.from_user.id)

    if not farzandlar:
        await callback.message.edit_text(
            f"✅ <b>{ism}</b> ro'yxatdan olib tashlandi.\n\n"
            "Farzandlar ro'yxati bo'sh.",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "👨‍👩‍👦 <b>Farzandlaringiz ro'yxati:</b>",
            parse_mode="HTML",
            reply_markup=farzandlar_keyboard(farzandlar)
        )
    await callback.answer(f"✅ {ism} o'chirildi")


@router.callback_query(F.data == "parent_back")
async def farzandlar_orqaga(callback: CallbackQuery):
    farzandlar = parent_farzandlar(callback.from_user.id)
    await callback.message.edit_text(
        "👨‍👩‍👦 <b>Farzandlaringiz ro'yxati:</b>",
        parse_mode="HTML",
        reply_markup=farzandlar_keyboard(farzandlar)
    )
    await callback.answer()


@router.callback_query(F.data == "parent_add")
async def farzand_qoshish_boshlash(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ParentStates.kod_kutish)
    await callback.message.edit_text(
        "📝 <b>Farzandingizning shaxsiy kodini kiriting:</b>\n\n"
        "Masalan: <code>A007</code> yoki <code>52B</code>",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ParentStates.kod_kutish)
async def farzand_kodi_kiritildi(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    await state.clear()

    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer(
            f"❌ <b>{kod}</b> kodli talaba topilmadi.\n\n"
            "Iltimos, to'g'ri kodni kiriting.",
            parse_mode="HTML"
        )
        return

    parent_qosh(message.from_user.id, kod)
    natijalar = talaba_natijalari(kod, limit=3)
    rank_info = get_student_rank(kod)
    matn = natija_matn_yasash(talaba, natijalar, rank_info)

    await message.answer(
        f"✅ <b>{talaba.get('ismlar')}</b> muvaffaqiyatli qo'shildi!\n\n" + matn,
        parse_mode="HTML"
    )


# ─── Yangi natija kelganda ota-onalarga xabar yuborish ────────────────────────

async def ota_onalarga_xabar_yuborish(bot, talaba_kod: str, yangi_ball: float):
    """
    Yangi natija qo'shilganda barcha ulangan ota-onalarga
    avtomatik xabar yuboradi.

    Bu funksiyani database.natija_qosh() dan keyin chaqiring:
        await ota_onalarga_xabar_yuborish(bot, kod, ball)
    """
    ota_onalar = talaba_barcha_ota_onalari(talaba_kod)
    if not ota_onalar:
        return

    talaba = talaba_topish(talaba_kod)
    if not talaba:
        return

    ism = talaba.get("ismlar", talaba_kod)
    sinf = talaba.get("sinf", "—")

    if yangi_ball >= 160:
        baho = "🥇 A'lo natija!"
    elif yangi_ball >= 120:
        baho = "🥈 Yaxshi natija"
    elif yangi_ball >= 80:
        baho = "🥉 O'rtacha natija"
    else:
        baho = "📝 Natija keldi"

    xabar = (
        f"🔔 <b>Yangi natija!</b>\n\n"
        f"👤 Farzandingiz: <b>{ism}</b> ({sinf} sinf)\n"
        f"🎯 Ball: <b>{yangi_ball:.1f}</b>\n"
        f"{baho}\n\n"
        f"Batafsil ko'rish uchun <code>PARENT_{talaba_kod}</code> deb yozing."
    )

    for parent_id in ota_onalar:
        try:
            await bot.send_message(parent_id, xabar, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Ota-onaga xabar yuborib bo'lmadi (id={parent_id}): {e}")
