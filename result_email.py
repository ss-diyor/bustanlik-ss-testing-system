"""
Natija emaili yuborish — Admin moduli.

Admin panelidagi "📊 Natija emaili" tugmasi orqali ishga tushadi.

FSM oqimi:
    1. Kimga: O'quvchi (kod bo'yicha) YOKI Sinf bo'yicha
    2a. [O'quvchi] → Kod kiriting → Natija + email ko'rsatish → Tasdiqlash → Yuborish
    2b. [Sinf]     → Sinf tanlash  → Emailli o'quvchilar soni → Tasdiqlash → Yuborish

Integratsiya (admin.py):
    from result_email import router as result_email_router
    dp.include_router(result_email_router)

keyboards.py (admin_menu_keyboard ichiga qo'shish):
    [KeyboardButton(text="📊 Natija emaili")],

Migration (bir marta ishga tushiring):
    ALTER TABLE talabalar ADD COLUMN IF NOT EXISTS email TEXT DEFAULT NULL;

O'quvchining emailini qo'shish uchun:
    UPDATE talabalar SET email = 'student@example.com' WHERE kod = 'KOD123';
    (yoki admin.py dagi talaba tahrirlash oqimiga email maydoni qo'shing)
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

logger = logging.getLogger(__name__)
router = Router()

MAKTAB_LOGO_URL = (
    "https://raw.githubusercontent.com/ss-diyor/"
    "bustanlik-ss-testing-system/main/logo.png"
)
TELEGRAM_BOT_URL   = "https://t.me/BustanlikSStestingsystembot"
TELEGRAM_KANAL_URL = "https://t.me/Bustanlikspecializedschool"


# ─── FSM holatlari ────────────────────────────────────────────────────────────

class ResultEmail(StatesGroup):
    tur_tanlash       = State()   # O'quvchi / Sinf
    kod_kutish        = State()   # O'quvchi kodi kiritilishi
    sinf_tanlash      = State()   # Sinf tanlash (inline)
    tasdiq_kutish     = State()   # Yuborish tasdiqi


# ─── DB yordamchi funksiyalar ─────────────────────────────────────────────────

def _talaba_email_ol(kod: str) -> dict | None:
    """O'quvchini kodi bo'yicha topadi, email va natijani birgalikda qaytaradi."""
    from database import get_connection, release_connection
    import psycopg2.extras
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
                t.kod, t.ismlar, t.sinf, t.yonalish, t.email,
                n.majburiy, n.asosiy_1, n.asosiy_2, n.umumiy_ball,
                n.test_sanasi
            FROM talabalar t
            LEFT JOIN test_natijalari n ON n.id = (
                SELECT id FROM test_natijalari
                WHERE talaba_kod = t.kod
                ORDER BY test_sanasi DESC
                LIMIT 1
            )
            WHERE t.kod = %s
            """,
            (kod.upper(),),
        )
        row = cur.fetchone()
        cur.close()
        release_connection(conn)
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Talaba email olishda xato: {e}")
        return None


def _sinf_emailli_talabalar(sinf_nomi: str) -> list[dict]:
    """
    Berilgan sinfdagi email manzili bor o'quvchilarni
    so'nggi natijasi bilan qaytaradi.
    """
    from database import get_connection, release_connection
    import psycopg2.extras
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
                t.kod, t.ismlar, t.sinf, t.yonalish, t.email,
                n.majburiy, n.asosiy_1, n.asosiy_2, n.umumiy_ball,
                n.test_sanasi
            FROM talabalar t
            LEFT JOIN test_natijalari n ON n.id = (
                SELECT id FROM test_natijalari
                WHERE talaba_kod = t.kod
                ORDER BY test_sanasi DESC
                LIMIT 1
            )
            WHERE t.sinf = %s
              AND t.email IS NOT NULL AND t.email <> ''
              AND t.status = 'aktiv'
            ORDER BY t.ismlar
            """,
            (sinf_nomi,),
        )
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Sinf talabalar emaillarini olishda xato: {e}")
        return []


# ─── Admin tekshirish ─────────────────────────────────────────────────────────

async def _admin_tekshir(state: FSMContext, user_id: int) -> bool:
    from config import ADMIN_IDS
    data = await state.get_data()
    return data.get("admin_logged_in") or user_id in ADMIN_IDS


# ─── HTML email shabloni ──────────────────────────────────────────────────────

def _natija_html(talaba: dict) -> str:
    """
    Bitta o'quvchi uchun chiroyli natija HTML email quriladi.
    Natija yo'q bo'lsa ham xat yuboriladi — "hali test topshirilmagan" deyiladi.
    """
    ism       = talaba.get("ismlar") or "O'quvchi"
    sinf      = talaba.get("sinf") or "—"
    yonalish  = talaba.get("yonalish") or "—"
    majburiy  = talaba.get("majburiy")
    asosiy_1  = talaba.get("asosiy_1")
    asosiy_2  = talaba.get("asosiy_2")
    umumiy    = talaba.get("umumiy_ball")
    sana      = talaba.get("test_sanasi")

    if sana:
        try:
            from datetime import datetime, timezone
            if isinstance(sana, str):
                sana_str = sana[:10]
            else:
                sana_str = sana.strftime("%Y-%m-%d")
        except Exception:
            sana_str = str(sana)[:10]
    else:
        sana_str = None

    # Natija mavjudmi?
    if umumiy is not None:
        natija_html = f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse; margin:16px 0;">
          <tr>
            <td style="padding:10px 14px; background:#f8faff; border:1px solid #e2e8f0;
                       border-radius:6px 0 0 0; font-size:13px; color:#6b7280; width:55%;">
              📚 Majburiy fan
            </td>
            <td style="padding:10px 14px; background:#f8faff; border:1px solid #e2e8f0;
                       border-top:1px solid #e2e8f0; text-align:right;
                       font-size:14px; font-weight:700; color:#1a3a8f;">
              {majburiy or 0} / 30
            </td>
          </tr>
          <tr>
            <td style="padding:10px 14px; background:#fff; border:1px solid #e2e8f0;
                       font-size:13px; color:#6b7280;">
              📘 Asosiy fan 1
            </td>
            <td style="padding:10px 14px; background:#fff; border:1px solid #e2e8f0;
                       text-align:right; font-size:14px; font-weight:700; color:#1a3a8f;">
              {asosiy_1 or 0} / 30
            </td>
          </tr>
          <tr>
            <td style="padding:10px 14px; background:#f8faff; border:1px solid #e2e8f0;
                       font-size:13px; color:#6b7280;">
              📗 Asosiy fan 2
            </td>
            <td style="padding:10px 14px; background:#f8faff; border:1px solid #e2e8f0;
                       text-align:right; font-size:14px; font-weight:700; color:#1a3a8f;">
              {asosiy_2 or 0} / 10
            </td>
          </tr>
          <tr>
            <td style="padding:12px 14px; background:#1a3a8f; border:1px solid #1a3a8f;
                       border-radius:0 0 0 6px; font-size:13px; color:#a0b4e8; font-weight:600;">
              🏆 Umumiy ball
            </td>
            <td style="padding:12px 14px; background:#1a3a8f; border:1px solid #1a3a8f;
                       border-radius:0 0 6px 0; text-align:right;
                       font-size:18px; font-weight:700; color:#fff;">
              {umumiy}
            </td>
          </tr>
        </table>
        {"<p style='font-size:12px; color:#9ca3af; margin:4px 0 0;'>📅 Test sanasi: " + sana_str + "</p>" if sana_str else ""}
        """
    else:
        natija_html = """
        <div style="background:#fff7ed; border:1px solid #fed7aa; border-radius:8px;
                    padding:16px; margin:16px 0; text-align:center;">
          <p style="margin:0; font-size:14px; color:#92400e;">
            ⚠️ Hali test natijasi kiritilmagan.
          </p>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Test natijangiz</title>
</head>
<body style="margin:0; padding:0; background:#f0f4f8; font-family:Arial,Helvetica,sans-serif;">
<div style="width:100%; background:#f0f4f8; padding:24px 0; box-sizing:border-box;">
  <div style="background:#fff; border-radius:12px; overflow:hidden; max-width:540px;
              margin:0 auto; box-shadow:0 4px 20px rgba(0,0,0,.10); width:92%;">

    <!-- Logo -->
    <div style="text-align:center; padding:28px 24px 16px;">
      <img src="{MAKTAB_LOGO_URL}" alt="Bo'stonliq maktabi"
           style="width:130px; max-width:55%; height:auto; display:block; margin:0 auto;">
    </div>
    <hr style="border:none; border-top:1px solid #e2e8f0; margin:0;">

    <!-- Sarlavha -->
    <div style="background:#1a3a8f; padding:22px 28px;">
      <p style="margin:0 0 6px; font-size:11px; color:#a0b4e8; letter-spacing:1.5px;">📊 TEST NATIJASI</p>
      <h1 style="margin:0; font-size:20px; color:#fff; line-height:1.4; font-weight:700;">
        Shaxsiy test natijangiz
      </h1>
    </div>

    <!-- Talaba ma'lumoti -->
    <div style="padding:24px 28px 4px;">
      <p style="margin:0 0 4px; font-size:16px; color:#1a3a8f; font-weight:700;">
        Hurmatli {ism},
      </p>
      <p style="margin:0 0 12px; font-size:13px; color:#6b7280;">
        🏫 Sinf: <b>{sinf}</b> &nbsp;|&nbsp; 📌 Yo'nalish: <b>{yonalish}</b>
      </p>
      <p style="margin:0; font-size:14px; color:#374151;">
        Quyida sizning eng so'nggi test natijangiz keltirilgan:
      </p>
    </div>

    <!-- Natija jadvali -->
    <div style="padding:0 28px 16px;">
      {natija_html}
    </div>

    <!-- Tugmalar -->
    <div style="padding:4px 28px 24px;">
      <a href="{TELEGRAM_BOT_URL}" target="_blank"
         style="display:inline-block; background:#1a3a8f; color:#fff; font-size:13px;
                font-weight:600; text-decoration:none; padding:11px 22px;
                border-radius:8px; margin:0 8px 8px 0;">
        🤖 Botda ko'rish
      </a>
      <a href="{TELEGRAM_KANAL_URL}" target="_blank"
         style="display:inline-block; background:#1a3a8f; color:#fff; font-size:13px;
                font-weight:600; text-decoration:none; padding:11px 22px;
                border-radius:8px; margin:0 0 8px 0;">
        📢 Kanal
      </a>
    </div>

    <!-- Footer -->
    <div style="background:#f1f5f9; padding:18px 28px; border-top:1px solid #e2e8f0; text-align:center;">
      <p style="margin:0 0 4px; font-size:12px; color:#6b7280;">
        <a href="{TELEGRAM_KANAL_URL}"
           style="color:#1a3a8f; text-decoration:none; font-weight:600;">
          Bo'stonliq tuman ixtisoslashtirilgan maktabi
        </a>
      </p>
      <p style="margin:0; font-size:12px; color:#6b7280;">© 2026 Barcha huquqlar himoyalangan.</p>
    </div>

  </div>
  <p style="margin:16px 0 0; font-size:11px; color:#9ca3af; text-align:center;">
    Bu xabar avtomatik tarzda yuborildi.
  </p>
</div>
</body>
</html>"""


# ─── Inline klaviaturalar ─────────────────────────────────────────────────────

def _tur_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 O'quvchi (kod bo'yicha)",  callback_data="remail:tur:talaba")],
        [InlineKeyboardButton(text="🏫 Sinf bo'yicha (hammasi)", callback_data="remail:tur:sinf")],
        [InlineKeyboardButton(text="❌ Bekor qilish",             callback_data="remail:tur:cancel")],
    ])


def _sinf_keyboard(sinflar: list):
    buttons = [
        [InlineKeyboardButton(text=f"🎓 {s}", callback_data=f"remail:sinf:{s}")]
        for s in sinflar
    ]
    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="remail:sinf:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _tasdiq_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha, yuborish",  callback_data="remail:tasdiq:ha")],
        [InlineKeyboardButton(text="❌ Bekor qilish",  callback_data="remail:tasdiq:yoq")],
    ])


# ─── 1-qadam: Boshlash ────────────────────────────────────────────────────────

@router.message(F.text == "📊 Natija emaili")
async def result_email_start(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        await message.answer("⛔ Ruxsat yo'q.")
        return

    await state.set_state(ResultEmail.tur_tanlash)
    await message.answer(
        "📊 <b>Natija emaili yuborish</b>\n\n"
        "Kimga yubormoqchisiz?",
        parse_mode="HTML",
        reply_markup=_tur_keyboard(),
    )


# ─── 2-qadam: Tur tanlash (O'quvchi / Sinf) ──────────────────────────────────

@router.callback_query(ResultEmail.tur_tanlash, F.data.startswith("remail:tur:"))
async def result_email_tur(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[-1]

    if action == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Bekor qilindi.")
        await callback.answer()
        return

    if action == "talaba":
        await state.set_state(ResultEmail.kod_kutish)
        await callback.message.edit_text(
            "👤 <b>O'quvchi kodi</b>\n\n"
            "O'quvchining kodini kiriting:\n"
            "<i>Masalan: ABC123</i>",
            parse_mode="HTML",
        )

    elif action == "sinf":
        from database import sinf_ol
        sinflar = sinf_ol()
        if not sinflar:
            await callback.message.edit_text("⚠️ Hech qanday sinf topilmadi.")
            await state.clear()
            await callback.answer()
            return

        await state.set_state(ResultEmail.sinf_tanlash)
        await callback.message.edit_text(
            "🏫 <b>Sinf tanlang:</b>",
            parse_mode="HTML",
            reply_markup=_sinf_keyboard(sinflar),
        )

    await callback.answer()


# ─── 3a-qadam: O'quvchi kodi qabul qilish ────────────────────────────────────

@router.message(ResultEmail.kod_kutish)
async def result_email_kod(message: Message, state: FSMContext):
    kod = (message.text or "").strip().upper()
    if not kod:
        await message.answer("❌ Kod bo'sh. Qayta kiriting:")
        return

    talaba = _talaba_email_ol(kod)

    if not talaba:
        await message.answer(
            f"⚠️ <b>{kod}</b> kodli o'quvchi topilmadi.\n"
            "Kodni tekshirib qayta kiriting:",
            parse_mode="HTML",
        )
        return

    email = talaba.get("email")
    if not email:
        await message.answer(
            f"⚠️ <b>{talaba['ismlar']}</b> ning email manzili bazada yo'q.\n\n"
            "Bazaga email qo'shish uchun:\n"
            "<code>UPDATE talabalar SET email = 'email@example.com' WHERE kod = '{kod}';</code>",
            parse_mode="HTML",
        )
        await state.clear()
        return

    umumiy = talaba.get("umumiy_ball")
    natija_text = (
        f"📊 Ball: <b>{umumiy}</b>"
        if umumiy is not None
        else "⚠️ Natija hali yo'q"
    )

    await state.update_data(
        remail_tur="talaba",
        remail_talabalar=[talaba],
    )
    await state.set_state(ResultEmail.tasdiq_kutish)

    await message.answer(
        f"👤 <b>{talaba['ismlar']}</b>\n"
        f"📧 Email: <code>{email}</code>\n"
        f"🏫 Sinf: {talaba.get('sinf', '—')}\n"
        f"{natija_text}\n\n"
        "Email yuborisinmi?",
        parse_mode="HTML",
        reply_markup=_tasdiq_keyboard(),
    )


# ─── 3b-qadam: Sinf tanlash ───────────────────────────────────────────────────

@router.callback_query(ResultEmail.sinf_tanlash, F.data.startswith("remail:sinf:"))
async def result_email_sinf(callback: CallbackQuery, state: FSMContext):
    sinf_nomi = callback.data[len("remail:sinf:"):]

    if sinf_nomi == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Bekor qilindi.")
        await callback.answer()
        return

    talabalar = _sinf_emailli_talabalar(sinf_nomi)

    if not talabalar:
        await callback.message.edit_text(
            f"⚠️ <b>{sinf_nomi}</b> sinfida email manzili bor o'quvchi topilmadi.\n\n"
            "O'quvchilarga email qo'shib, qayta urinib ko'ring.",
            parse_mode="HTML",
        )
        await state.clear()
        await callback.answer()
        return

    await state.update_data(
        remail_tur="sinf",
        remail_sinf=sinf_nomi,
        remail_talabalar=talabalar,
    )
    await state.set_state(ResultEmail.tasdiq_kutish)

    await callback.message.edit_text(
        f"🏫 <b>{sinf_nomi}</b>\n"
        f"📧 Email bor o'quvchilar: <b>{len(talabalar)} ta</b>\n\n"
        f"Natija emaili yuborisinmi?",
        parse_mode="HTML",
        reply_markup=_tasdiq_keyboard(),
    )
    await callback.answer()


# ─── 4-qadam: Tasdiqlash → Yuborish ──────────────────────────────────────────

@router.callback_query(ResultEmail.tasdiq_kutish, F.data.startswith("remail:tasdiq:"))
async def result_email_tasdiq(callback: CallbackQuery, state: FSMContext):
    action = callback.data.split(":")[-1]

    if action == "yoq":
        await state.clear()
        await callback.message.edit_text("❌ Bekor qilindi.")
        await callback.answer()
        return

    data      = await state.get_data()
    talabalar = data.get("remail_talabalar", [])
    await state.clear()

    if not talabalar:
        await callback.message.edit_text("⚠️ O'quvchi ma'lumotlari topilmadi.")
        await callback.answer()
        return

    await callback.message.edit_text(
        f"⏳ {len(talabalar)} ta email yuborilmoqda..."
    )
    await callback.answer()

    from brevo_email import send_email
    import asyncio

    ok = fail = skip = 0
    for i, talaba in enumerate(talabalar):
        email = talaba.get("email")
        if not email:
            skip += 1
            continue

        # Rate limit: har 50 ta so'ngra 1 soniya kutish
        if i > 0 and i % 50 == 0:
            await asyncio.sleep(1.0)

        html    = _natija_html(talaba)
        subject = "📊 Test natijangiz — Bustanlik SS Testing System"
        success = await send_email(
            to_email=email,
            to_name=talaba.get("ismlar") or "O'quvchi",
            subject=subject,
            html_content=html,
        )
        if success:
            ok += 1
        else:
            fail += 1

    # Natija xabari
    sinf_label = data.get("remail_sinf", "")
    qayerga    = f"🏫 Sinf: <b>{sinf_label}</b>\n" if sinf_label else ""

    await callback.message.answer(
        f"📧 <b>Natija emaili yuborish yakunlandi!</b>\n\n"
        f"{qayerga}"
        f"✅ Muvaffaqiyatli: <b>{ok} ta</b>\n"
        f"❌ Xato: <b>{fail} ta</b>\n"
        + (f"⏭️ Email yo'q (o'tkazildi): <b>{skip} ta</b>\n" if skip else ""),
        parse_mode="HTML",
    )
