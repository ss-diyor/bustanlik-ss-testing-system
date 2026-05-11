"""
payment.py — Franchise obuna va to'lov tizimi

Rollar:
  Super admin  (ADMIN_IDS)  — hamma narsaga kiradi, to'lovlarni tasdiqlaydi
  Maktab admin              — o'z maktabini boshqaradi, obuna to'laydi
  O'quvchi                  — faqat natijalarini ko'radi

To'lov jarayoni:
  1. Maktab admin → "💳 Obuna to'lash" → karta raqami ko'rsatiladi
  2. Admin to'lov qiladi va chek yuboradi
  3. Super adminga xabar ketadi → tasdiqlaydi / rad etadi
  4. Tasdiqlansa: obuna_tugash_sana = bugun + 30 kun
  5. Maktab adminga natija xabari yuboriladi
"""

import logging
from datetime import date, timedelta

from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, KARTA_RAQAMI, OYLIK_NARX
import database as db

logger = logging.getLogger(__name__)
router = Router()


# ── FSM ────────────────────────────────────────────────────────────────────
class PaymentFSM(StatesGroup):
    chek_kutish = State()          # Maktab admin chek rasmini yuklayapti
    rad_sababi   = State()         # Super admin rad sababi kiritmoqda


class MaktabAdminFSM(StatesGroup):
    admin_qoshish = State()        # Super admin: yangi maktab admini TG ID kiritmoqda


# ── DB funksiyalari ─────────────────────────────────────────────────────────

def create_payment_tables():
    """Yangi jadvallar va ustunlarni yaratish (migration)."""
    conn = db.get_connection()
    cur = conn.cursor()

    # maktablar jadvaliga yangi ustunlar
    migrations = [
        "ALTER TABLE maktablar ADD COLUMN IF NOT EXISTS admin_telegram_id BIGINT",
        "ALTER TABLE maktablar ADD COLUMN IF NOT EXISTS obuna_holati VARCHAR(20) DEFAULT 'inactive'",
        "ALTER TABLE maktablar ADD COLUMN IF NOT EXISTS obuna_tugash_sana DATE",
        "ALTER TABLE maktablar ADD COLUMN IF NOT EXISTS oylik_narx INTEGER DEFAULT 300000",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_maktablar_admin_tg ON maktablar(admin_telegram_id) WHERE admin_telegram_id IS NOT NULL",
    ]
    for sql in migrations:
        try:
            cur.execute(sql)
        except Exception as e:
            conn.rollback()
            logger.warning(f"Migration skip: {e}")
            conn = db.get_connection()
            cur = conn.cursor()

    # tolovlar jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tolovlar (
            id               SERIAL PRIMARY KEY,
            maktab_id        INTEGER NOT NULL REFERENCES maktablar(id) ON DELETE CASCADE,
            admin_telegram_id BIGINT NOT NULL,
            summa            INTEGER NOT NULL,
            chek_foto_id     TEXT,
            holat            VARCHAR(20) DEFAULT 'pending',
            tasdiqlagan_id   BIGINT,
            rad_sababi       TEXT,
            yaratilgan       TIMESTAMP DEFAULT NOW(),
            yangilangan      TIMESTAMP DEFAULT NOW()
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_tolovlar_holat ON tolovlar(holat)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_tolovlar_maktab ON tolovlar(maktab_id)"
    )

    # payment_enabled sozlamasi (standart: False — majburiy emas)
    cur.execute(
        "INSERT INTO settings (key, value) VALUES ('payment_enabled', 'False') ON CONFLICT DO NOTHING"
    )

    conn.commit()
    cur.close()
    db.release_connection(conn)


def get_maktab_by_admin(telegram_id: int) -> dict | None:
    """Telegram ID bo'yicha maktab ma'lumotlarini qaytaradi."""
    conn = db.get_connection()
    cur = conn.cursor(cursor_factory=__import__('psycopg2').extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM maktablar WHERE admin_telegram_id = %s",
        (telegram_id,)
    )
    row = cur.fetchone()
    cur.close()
    db.release_connection(conn)
    return dict(row) if row else None


def is_maktab_admin(telegram_id: int) -> bool:
    """Bu foydalanuvchi biron maktabning admini ekanini tekshiradi."""
    return get_maktab_by_admin(telegram_id) is not None


def is_subscription_active(telegram_id: int) -> bool:
    """
    Obuna faol ekanini tekshiradi.
    payment_enabled=False bo'lsa — har doim True qaytaradi.
    """
    if db.get_setting("payment_enabled", "False") != "True":
        return True  # To'lov rejimi o'chirilgan → hamma kiradi

    maktab = get_maktab_by_admin(telegram_id)
    if not maktab:
        return False

    holat = maktab.get("obuna_holati", "inactive")
    tugash = maktab.get("obuna_tugash_sana")

    if holat == "active" and tugash and tugash >= date.today():
        return True
    return False


def subscription_days_left(telegram_id: int) -> int:
    """Obunada qolgan kunlar soni (muddati o'tgan bo'lsa 0)."""
    maktab = get_maktab_by_admin(telegram_id)
    if not maktab:
        return 0
    tugash = maktab.get("obuna_tugash_sana")
    if not tugash:
        return 0
    delta = tugash - date.today()
    return max(0, delta.days)


def create_payment_request(maktab_id: int, admin_tg_id: int, summa: int, chek_foto_id: str) -> int:
    """Yangi to'lov so'rovi yaratadi, ID qaytaradi."""
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO tolovlar (maktab_id, admin_telegram_id, summa, chek_foto_id, holat)
        VALUES (%s, %s, %s, %s, 'pending') RETURNING id
        """,
        (maktab_id, admin_tg_id, summa, chek_foto_id)
    )
    payment_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    db.release_connection(conn)
    return payment_id


def get_payment(payment_id: int) -> dict | None:
    conn = db.get_connection()
    cur = conn.cursor(cursor_factory=__import__('psycopg2').extras.RealDictCursor)
    cur.execute(
        """
        SELECT t.*, m.nomi as maktab_nomi, m.oylik_narx
        FROM tolovlar t
        JOIN maktablar m ON m.id = t.maktab_id
        WHERE t.id = %s
        """,
        (payment_id,)
    )
    row = cur.fetchone()
    cur.close()
    db.release_connection(conn)
    return dict(row) if row else None


def get_pending_payments() -> list[dict]:
    conn = db.get_connection()
    cur = conn.cursor(cursor_factory=__import__('psycopg2').extras.RealDictCursor)
    cur.execute(
        """
        SELECT t.*, m.nomi as maktab_nomi
        FROM tolovlar t
        JOIN maktablar m ON m.id = t.maktab_id
        WHERE t.holat = 'pending'
        ORDER BY t.yaratilgan ASC
        """
    )
    rows = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    return [dict(r) for r in rows]


def approve_payment(payment_id: int, super_admin_id: int) -> dict | None:
    """To'lovni tasdiqlaydi va obunani 30 kunga uzaytiradi."""
    conn = db.get_connection()
    cur = conn.cursor(cursor_factory=__import__('psycopg2').extras.RealDictCursor)

    # To'lov ma'lumotlarini olish
    cur.execute("SELECT * FROM tolovlar WHERE id = %s AND holat = 'pending'", (payment_id,))
    payment = cur.fetchone()
    if not payment:
        cur.close()
        db.release_connection(conn)
        return None

    payment = dict(payment)
    maktab_id = payment["maktab_id"]

    # Mavjud tugash sanasini olish
    cur.execute("SELECT obuna_tugash_sana FROM maktablar WHERE id = %s", (maktab_id,))
    row = cur.fetchone()
    tugash = row[0] if row and row[0] else None

    # Agar obuna hali tugamagan bo'lsa — unga 30 kun qo'shiladi
    baza = tugash if (tugash and tugash >= date.today()) else date.today()
    yangi_tugash = baza + timedelta(days=30)

    # Maktab obunasini yangilash
    cur.execute(
        """
        UPDATE maktablar
        SET obuna_holati = 'active', obuna_tugash_sana = %s
        WHERE id = %s
        """,
        (yangi_tugash, maktab_id)
    )

    # To'lov holatini yangilash
    cur.execute(
        """
        UPDATE tolovlar
        SET holat = 'approved', tasdiqlagan_id = %s, yangilangan = NOW()
        WHERE id = %s
        """,
        (super_admin_id, payment_id)
    )

    conn.commit()
    cur.close()
    db.release_connection(conn)
    payment["yangi_tugash"] = yangi_tugash
    return payment


def reject_payment(payment_id: int, super_admin_id: int, sabab: str) -> dict | None:
    """To'lovni rad etadi."""
    conn = db.get_connection()
    cur = conn.cursor(cursor_factory=__import__('psycopg2').extras.RealDictCursor)
    cur.execute(
        """
        UPDATE tolovlar
        SET holat = 'rejected', tasdiqlagan_id = %s, rad_sababi = %s, yangilangan = NOW()
        WHERE id = %s AND holat = 'pending'
        RETURNING *
        """,
        (super_admin_id, sabab, payment_id)
    )
    row = cur.fetchone()
    conn.commit()
    cur.close()
    db.release_connection(conn)
    return dict(row) if row else None


def get_all_maktab_admins() -> list[dict]:
    """Barcha maktablar va ularning admin ma'lumotlarini qaytaradi."""
    conn = db.get_connection()
    cur = conn.cursor(cursor_factory=__import__('psycopg2').extras.RealDictCursor)
    cur.execute(
        """
        SELECT id, nomi, admin_telegram_id, obuna_holati,
               obuna_tugash_sana, oylik_narx
        FROM maktablar
        ORDER BY nomi
        """
    )
    rows = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    return [dict(r) for r in rows]


def set_maktab_admin(maktab_id: int, telegram_id: int | None) -> bool:
    """Maktabga admin telegram ID biriktiradi yoki o'chiradi."""
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE maktablar SET admin_telegram_id = %s WHERE id = %s",
            (telegram_id, maktab_id)
        )
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"set_maktab_admin error: {e}")
        return False
    finally:
        cur.close()
        db.release_connection(conn)


def get_maktab_payment_history(maktab_id: int, limit: int = 5) -> list[dict]:
    conn = db.get_connection()
    cur = conn.cursor(cursor_factory=__import__('psycopg2').extras.RealDictCursor)
    cur.execute(
        """
        SELECT * FROM tolovlar WHERE maktab_id = %s
        ORDER BY yaratilgan DESC LIMIT %s
        """,
        (maktab_id, limit)
    )
    rows = cur.fetchall()
    cur.close()
    db.release_connection(conn)
    return [dict(r) for r in rows]


# ── Klaviaturalar ────────────────────────────────────────────────────────────

def payment_menu_keyboard() -> InlineKeyboardMarkup:
    """Maktab admin uchun to'lov menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 To'lov qilish", callback_data="payment_start")],
        [InlineKeyboardButton(text="📋 To'lov tarixi",  callback_data="payment_history")],
    ])


def payment_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="payment_cancel")],
    ])


def payment_review_keyboard(payment_id: int) -> InlineKeyboardMarkup:
    """Super admin uchun — tasdiq/rad tugmalari."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Tasdiqlash",
                callback_data=f"pay_approve:{payment_id}"
            ),
            InlineKeyboardButton(
                text="❌ Rad etish",
                callback_data=f"pay_reject:{payment_id}"
            ),
        ]
    ])


def maktab_admin_list_keyboard(maktablar: list[dict]) -> InlineKeyboardMarkup:
    """Maktab adminlarini boshqarish uchun klaviatura."""
    buttons = []
    for m in maktablar:
        admin_info = f"👤 {m['admin_telegram_id']}" if m.get("admin_telegram_id") else "➕ Admin yo'q"
        buttons.append([
            InlineKeyboardButton(
                text=f"🏫 {m['nomi']} — {admin_info}",
                callback_data=f"maktab_admin_edit:{m['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Ortga", callback_data="payment_settings_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Yordamchi ────────────────────────────────────────────────────────────────

def _holat_emoji(holat: str) -> str:
    return {"active": "✅", "inactive": "⏸", "expired": "❌", "blocked": "🚫"}.get(holat, "❓")


def _payment_holat_emoji(holat: str) -> str:
    return {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(holat, "❓")


# ── Maktab admin menyu handler ───────────────────────────────────────────────

async def show_school_admin_menu(message: Message, telegram_id: int):
    """Maktab admin asosiy menyusini ko'rsatadi."""
    maktab = get_maktab_by_admin(telegram_id)
    if not maktab:
        await message.answer("⚠️ Siz hech qaysi maktabga biriktirilmagansiz.")
        return

    payment_enabled = db.get_setting("payment_enabled", "False") == "True"
    active = is_subscription_active(telegram_id)
    days_left = subscription_days_left(telegram_id)

    if payment_enabled:
        if active:
            status_text = f"✅ Obuna faol — {days_left} kun qoldi"
            if days_left <= 5:
                status_text += " ⚠️"
        else:
            status_text = "❌ Obuna tugagan yoki faol emas"
    else:
        status_text = "🔓 To'lov rejimi o'chirilgan"

    text = (
        f"🏫 <b>{maktab['nomi']}</b>\n\n"
        f"📌 Obuna holati: {status_text}\n"
    )
    if payment_enabled and not active:
        text += (
            f"\n💳 Oylik to'lov: <b>{maktab.get('oylik_narx', OYLIK_NARX):,} so'm</b>\n\n"
            "To'lov qiling va chek yuboring — admin tasdiqlagandan so'ng "
            "botga to'liq kirish ochiladi."
        )
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="💳 Obuna to'lash")]],
            resize_keyboard=True
        )
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
    else:
        # Obuna faol — oddiy admin menyusini ko'rsatish
        from keyboards import admin_menu_keyboard
        await message.answer(
            text + "\n👇 Quyidagi menyudan foydalaning:",
            parse_mode="HTML",
            reply_markup=admin_menu_keyboard()
        )


# ── Handler: Maktab admin — To'lov boshlash ─────────────────────────────────

@router.message(F.text == "💳 Obuna to'lash")
async def payment_start_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    maktab = get_maktab_by_admin(user_id)
    if not maktab:
        return

    karta = KARTA_RAQAMI or db.get_setting("karta_raqami", "")
    narx = maktab.get("oylik_narx") or OYLIK_NARX

    if not karta:
        await message.answer(
            "⚠️ Karta raqami hali sozlanmagan. "
            "Iltimos, super adminga murojaat qiling."
        )
        return

    await state.set_state(PaymentFSM.chek_kutish)
    await state.update_data(maktab_id=maktab["id"], summa=narx)

    text = (
        f"💳 <b>To'lov ma'lumotlari</b>\n\n"
        f"🏫 Maktab: <b>{maktab['nomi']}</b>\n"
        f"💰 Summa: <b>{narx:,} so'm</b>\n\n"
        f"📋 To'lov uchun karta raqami:\n"
        f"<code>{karta}</code>\n\n"
        "✅ To'lov qilib bo'lgach, chek rasmini yuboring.\n"
        "📸 <i>Faqat rasm qabul qilinadi (screenshot yoki foto)</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=payment_cancel_keyboard())


@router.callback_query(F.data == "payment_start")
async def payment_start_cb(callback: CallbackQuery, state: FSMContext):
    await payment_start_message(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "payment_cancel")
async def payment_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    maktab = get_maktab_by_admin(callback.from_user.id)
    await callback.message.edit_text(
        "❌ To'lov bekor qilindi.",
        reply_markup=None
    )
    await callback.answer()


@router.message(PaymentFSM.chek_kutish, F.photo)
async def chek_qabul(message: Message, state: FSMContext, bot: Bot):
    """Maktab admin chek rasmini yubordi."""
    data = await state.get_data()
    maktab_id = data.get("maktab_id")
    summa = data.get("summa", OYLIK_NARX)

    # Eng katta rasmni olish
    photo = message.photo[-1]
    chek_foto_id = photo.file_id

    # DB ga yozish
    payment_id = create_payment_request(
        maktab_id=maktab_id,
        admin_tg_id=message.from_user.id,
        summa=summa,
        chek_foto_id=chek_foto_id
    )

    await state.clear()

    # Foydalanuvchiga tasdiqlash
    await message.answer(
        "✅ <b>Chek qabul qilindi!</b>\n\n"
        "⏳ Admin tekshirib, tez orada tasdiqlaydi.\n"
        "Tasdiqlangandan so'ng xabar olasiz.",
        parse_mode="HTML"
    )

    # Super adminlarga xabar yuborish
    maktab = get_maktab_by_admin(message.from_user.id)
    admin_nomi = (
        f"@{message.from_user.username}" if message.from_user.username
        else message.from_user.full_name
    )

    caption = (
        f"🔔 <b>Yangi to'lov so'rovi #{payment_id}</b>\n\n"
        f"🏫 Maktab: <b>{maktab['nomi'] if maktab else '?'}</b>\n"
        f"👤 Admin: {admin_nomi} (<code>{message.from_user.id}</code>)\n"
        f"💰 Summa: <b>{summa:,} so'm</b>\n\n"
        "Chekni tekshirib, qaror qiling:"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=chek_foto_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=payment_review_keyboard(payment_id)
            )
        except Exception as e:
            logger.error(f"Super adminga xabar yuborishda xato ({admin_id}): {e}")


@router.message(PaymentFSM.chek_kutish)
async def chek_noto_gri(message: Message, state: FSMContext):
    await message.answer(
        "📸 Iltimos, faqat <b>rasm</b> yuboring (chek screenshoti).",
        parse_mode="HTML",
        reply_markup=payment_cancel_keyboard()
    )


# ── Handler: Super admin — Tasdiqlash / Rad etish ───────────────────────────

@router.callback_query(F.data.startswith("pay_approve:"))
async def pay_approve_handler(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Ruxsat yo'q", show_alert=True)
        return

    payment_id = int(callback.data.split(":")[1])
    payment = approve_payment(payment_id, callback.from_user.id)

    if not payment:
        await callback.answer("⚠️ To'lov topilmadi yoki allaqachon ko'rib chiqilgan.", show_alert=True)
        return

    tugash = payment["yangi_tugash"]
    await callback.message.edit_caption(
        callback.message.caption + f"\n\n✅ <b>TASDIQLANDI</b> — obuna {tugash.strftime('%d.%m.%Y')} gacha",
        parse_mode="HTML",
        reply_markup=None
    )
    await callback.answer("✅ Tasdiqlandi")

    # Maktab adminga xabar
    try:
        await bot.send_message(
            chat_id=payment["admin_telegram_id"],
            text=(
                "🎉 <b>To'lovingiz tasdiqlandi!</b>\n\n"
                f"✅ Obuna faol\n"
                f"📅 Tugash sanasi: <b>{tugash.strftime('%d.%m.%Y')}</b>\n\n"
                "Botdan to'liq foydalanishingiz mumkin. /start bosing."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Maktab adminga xabar yuborishda xato: {e}")


@router.callback_query(F.data.startswith("pay_reject:"))
async def pay_reject_handler(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Ruxsat yo'q", show_alert=True)
        return

    payment_id = int(callback.data.split(":")[1])
    await state.set_state(PaymentFSM.rad_sababi)
    await state.update_data(reject_payment_id=payment_id, reject_msg_id=callback.message.message_id)
    await callback.message.answer(
        "✏️ Rad etish sababini yozing (maktab adminga yuboriladi):"
    )
    await callback.answer()


@router.message(PaymentFSM.rad_sababi)
async def rad_sababi_qabul(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    payment_id = data.get("reject_payment_id")
    sabab = message.text.strip()

    payment = reject_payment(payment_id, message.from_user.id, sabab)
    await state.clear()

    if not payment:
        await message.answer("⚠️ To'lov topilmadi yoki allaqachon ko'rib chiqilgan.")
        return

    await message.answer(f"❌ To'lov #{payment_id} rad etildi.")

    # Maktab adminga xabar
    try:
        await bot.send_message(
            chat_id=payment["admin_telegram_id"],
            text=(
                "❌ <b>To'lovingiz rad etildi</b>\n\n"
                f"📝 Sabab: {sabab}\n\n"
                "Qayta to'lov qilib, chek yuboring."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Maktab adminga rad xabarida xato: {e}")


# ── Handler: Super admin — To'lov tarixi ko'rish ────────────────────────────

@router.callback_query(F.data == "payment_history")
async def payment_history_handler(callback: CallbackQuery):
    maktab = get_maktab_by_admin(callback.from_user.id)
    if not maktab:
        await callback.answer("⛔ Ruxsat yo'q", show_alert=True)
        return

    tarix = get_maktab_payment_history(maktab["id"])
    if not tarix:
        await callback.message.edit_text("📋 To'lov tarixi bo'sh.")
        await callback.answer()
        return

    lines = [f"📋 <b>{maktab['nomi']} — To'lov tarixi</b>\n"]
    for t in tarix:
        emoji = _payment_holat_emoji(t["holat"])
        sana = t["yaratilgan"].strftime("%d.%m.%Y")
        lines.append(
            f"{emoji} {sana} — {t['summa']:,} so'm ({t['holat']})"
            + (f"\n   ↳ Sabab: {t['rad_sababi']}" if t.get("rad_sababi") else "")
        )

    await callback.message.edit_text(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Ortga", callback_data="payment_back")]
        ])
    )
    await callback.answer()


# ── Handler: Super admin — Maktab adminlarini boshqarish ────────────────────

@router.callback_query(F.data == "manage_maktab_admins")
async def manage_maktab_admins(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Ruxsat yo'q", show_alert=True)
        return

    maktablar = get_all_maktab_admins()
    await callback.message.edit_text(
        "🏫 <b>Maktab adminlari</b>\n\n"
        "Maktabni tanlang — admin biriktirasiz yoki o'zgartirасiz:",
        parse_mode="HTML",
        reply_markup=maktab_admin_list_keyboard(maktablar)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("maktab_admin_edit:"))
async def maktab_admin_edit(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Ruxsat yo'q", show_alert=True)
        return

    maktab_id = int(callback.data.split(":")[1])
    await state.set_state(MaktabAdminFSM.admin_qoshish)
    await state.update_data(edit_maktab_id=maktab_id)

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT nomi, admin_telegram_id FROM maktablar WHERE id = %s", (maktab_id,))
    row = cur.fetchone()
    cur.close()
    db.release_connection(conn)

    if not row:
        await callback.answer("Maktab topilmadi", show_alert=True)
        return

    nomi, admin_tg = row
    mavjud = f"Hozirgi admin ID: <code>{admin_tg}</code>" if admin_tg else "Hozircha admin biriktirilmagan"

    await callback.message.edit_text(
        f"🏫 <b>{nomi}</b>\n\n"
        f"{mavjud}\n\n"
        "Yangi admin Telegram ID sini kiriting:\n"
        "<i>(0 kiriting — adminni o'chirish uchun)</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor", callback_data="manage_maktab_admins")]
        ])
    )
    await callback.answer()


@router.message(MaktabAdminFSM.admin_qoshish)
async def maktab_admin_id_qabul(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    data = await state.get_data()
    maktab_id = data.get("edit_maktab_id")

    try:
        tg_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Faqat son kiriting (Telegram ID).")
        return

    new_id = None if tg_id == 0 else tg_id
    ok = set_maktab_admin(maktab_id, new_id)
    await state.clear()

    if ok:
        if new_id:
            await message.answer(
                f"✅ Maktabga admin biriktirildi: <code>{new_id}</code>\n\n"
                "Maktab admin /start bosib botga kirishi mumkin.",
                parse_mode="HTML"
            )
        else:
            await message.answer("✅ Admin o'chirildi.")
    else:
        await message.answer(
            "❌ Xato: bu Telegram ID boshqa maktabga biriktirilgan bo'lishi mumkin."
        )
