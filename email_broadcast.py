"""
Email orqali e'lon yuborish — Admin moduli.

Admin menyusida "📧 Email xabar yuborish" tugmasi bosiganda ishga tushadi.
FSM oqimi:
    1. Mavzu (subject) so'rash
    2. Xabar matni so'rash
    3. Kimga: o'quvchilar / ota-onalar / hammasi — tanlash
    4. Tasdiqlash → Brevo orqali yuborish

Integratsiya (admin.py):
    from email_broadcast import router as email_broadcast_router
    dp.include_router(email_broadcast_router)

keyboards.py (admin_menu_keyboard ichiga qo'shish):
    [KeyboardButton(text="📧 Email xabar yuborish")],
"""

import logging
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from brevo_email import send_bulk_emails, build_announcement_html

logger = logging.getLogger(__name__)
router = Router()


# ─── FSM holatlari ────────────────────────────────────────────────────────────

class EmailBroadcast(StatesGroup):
    mavzu_kutish  = State()
    matn_kutish   = State()
    kimga_tanlash = State()
    tasdiq_kutish = State()


# ─── Ma'lumotlar bazasidan emaillarni olish ───────────────────────────────────

def _get_student_emails() -> list[dict]:
    from database import get_connection, release_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ismlar, email
            FROM talabalar
            WHERE email IS NOT NULL AND email <> '' AND status = 'aktiv'
        """)
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return [{"name": r[0] or "O'quvchi", "email": r[1]} for r in rows]
    except Exception as e:
        logger.error(f"O'quvchi emaillarini olishda xato: {e}")
        return []


def _get_parent_emails() -> list[dict]:
    from database import get_connection, release_connection
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ismlar, parent_email
            FROM talabalar
            WHERE parent_email IS NOT NULL AND parent_email <> '' AND status = 'aktiv'
        """)
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return [
            {"name": f"{r[0] or 'Oquvchi'} ota-onasi", "email": r[1]}
            for r in rows
        ]
    except Exception as e:
        logger.error(f"Ota-ona emaillarini olishda xato: {e}")
        return []


# ─── Yordamchi: admin tekshirish ─────────────────────────────────────────────

async def _admin_tekshir(state: FSMContext, user_id: int) -> bool:
    from config import ADMIN_IDS
    data = await state.get_data()
    return data.get("admin_logged_in") or user_id in ADMIN_IDS


# ─── Inline klaviaturalar ─────────────────────────────────────────────────────

def _kimga_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 O'quvchilar",   callback_data="ebcast:students")],
        [InlineKeyboardButton(text="👨‍👩‍👦 Ota-onalar",    callback_data="ebcast:parents")],
        [InlineKeyboardButton(text="👥 Hammasi",        callback_data="ebcast:all")],
        [InlineKeyboardButton(text="❌ Bekor qilish",   callback_data="ebcast:cancel")],
    ])


def _tasdiq_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, yuborish",   callback_data="ebcast:confirm")],
        [InlineKeyboardButton(text="❌ Bekor qilish",   callback_data="ebcast:cancel")],
    ])


# ─── 1-qadam: Boshlash ────────────────────────────────────────────────────────

@router.message(F.text == "📧 Email xabar yuborish")
async def email_broadcast_start(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        await message.answer("⛔ Ruxsat yo'q.")
        return

    await state.set_state(EmailBroadcast.mavzu_kutish)
    await message.answer(
        "📧 <b>Email e'lon yuborish</b>\n\n"
        "<b>1-qadam:</b> Email mavzusini kiriting:\n"
        "<i>Masalan: Dars jadvali o'zgardi</i>",
        parse_mode="HTML",
    )


# ─── 2-qadam: Mavzu qabul → Matn so'rash ─────────────────────────────────────

@router.message(EmailBroadcast.mavzu_kutish)
async def email_broadcast_mavzu(message: Message, state: FSMContext):
    mavzu = (message.text or "").strip()
    if not mavzu:
        await message.answer("❌ Mavzu bo'sh bo'lmasin. Qayta kiriting:")
        return

    await state.update_data(mavzu=mavzu)
    await state.set_state(EmailBroadcast.matn_kutish)
    await message.answer(
        f"✅ Mavzu: <b>{mavzu}</b>\n\n"
        "<b>2-qadam:</b> Xabar matnini kiriting:\n"
        "<i>(Ko'p qatorli bo'lishi mumkin)</i>",
        parse_mode="HTML",
    )


# ─── 3-qadam: Matn qabul → Kimga tanlash ─────────────────────────────────────

@router.message(EmailBroadcast.matn_kutish)
async def email_broadcast_matn(message: Message, state: FSMContext):
    matn = (message.text or "").strip()
    if not matn:
        await message.answer("❌ Matn bo'sh bo'lmasin. Qayta kiriting:")
        return

    await state.update_data(matn=matn)
    await state.set_state(EmailBroadcast.kimga_tanlash)

    data = await state.get_data()
    await message.answer(
        f"📄 <b>Mavzu:</b> {data['mavzu']}\n"
        f"📝 <b>Matn:</b> {matn[:200]}{'...' if len(matn) > 200 else ''}\n\n"
        "<b>3-qadam:</b> Kimga yubormoqchisiz?",
        parse_mode="HTML",
        reply_markup=_kimga_keyboard(),
    )


# ─── 4-qadam: Kimga tanlash → Tasdiqlash ─────────────────────────────────────

@router.callback_query(EmailBroadcast.kimga_tanlash, F.data.startswith("ebcast:"))
async def email_broadcast_kimga(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Email yuborish bekor qilindi.")
        return

    kimga_map = {
        "students": "🎓 O'quvchilar",
        "parents":  "👨‍👩‍👦 Ota-onalar",
        "all":      "👥 Hammasi",
    }
    kimga_label = kimga_map.get(action, action)

    students   = _get_student_emails() if action in ("students", "all") else []
    parents    = _get_parent_emails()  if action in ("parents",  "all") else []
    recipients = {r["email"]: r for r in students + parents}
    jami = len(recipients)

    await state.update_data(kimga=action)
    await state.set_state(EmailBroadcast.tasdiq_kutish)

    data = await state.get_data()
    await callback.message.edit_text(
        f"📬 <b>Tasdiqlash</b>\n\n"
        f"📌 Mavzu: <b>{data['mavzu']}</b>\n"
        f"👥 Kimga: <b>{kimga_label}</b>\n"
        f"📊 Email topildi: <b>{jami} ta</b>\n\n"
        f"Yuborilsinmi?",
        parse_mode="HTML",
        reply_markup=_tasdiq_keyboard(),
    )
    await callback.answer()


# ─── 5-qadam: Tasdiqlash → Yuborish ──────────────────────────────────────────

@router.callback_query(EmailBroadcast.tasdiq_kutish, F.data.startswith("ebcast:"))
async def email_broadcast_tasdiq(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[1]

    if action == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Email yuborish bekor qilindi.")
        return

    if action != "confirm":
        return

    data  = await state.get_data()
    kimga = data.get("kimga", "all")
    mavzu = data["mavzu"]
    matn  = data["matn"]

    await state.clear()
    await callback.message.edit_text("⏳ Emaillar yuborilmoqda, iltimos kuting...")

    # Recipientlarni yig'ish
    students   = _get_student_emails() if kimga in ("students", "all") else []
    parents    = _get_parent_emails()  if kimga in ("parents",  "all") else []
    all_dict   = {r["email"]: r for r in students + parents}
    recipients = list(all_dict.values())

    if not recipients:
        await callback.message.answer(
            "⚠️ Hech qanday email manzili topilmadi.\n"
            "O'quvchi yoki ota-ona email manzillari bazaga qo'shilmagan."
        )
        return

    # HTML bir marta quriladi — send_bulk_emails ichida qayta qurilmaydi
    html = build_announcement_html(title=mavzu, body=matn)
    ok, fail = await send_bulk_emails(recipients, subject=mavzu, html_content=html)

    kimga_labels = {
        "students": "🎓 O'quvchilar",
        "parents":  "👨‍👩‍👦 Ota-onalar",
        "all":      "👥 Hammasi",
    }
    await callback.message.answer(
        f"📧 <b>Email yuborish yakunlandi!</b>\n\n"
        f"📌 Mavzu: <b>{mavzu}</b>\n"
        f"👥 Kimga: <b>{kimga_labels.get(kimga, kimga)}</b>\n"
        f"✅ Muvaffaqiyatli: <b>{ok} ta</b>\n"
        f"❌ Xato: <b>{fail} ta</b>",
        parse_mode="HTML",
    )
    await callback.answer()
