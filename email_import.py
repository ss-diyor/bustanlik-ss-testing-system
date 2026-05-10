"""
Excel fayl orqali o'quvchi/ota-ona emaillarini import qilish moduli.

Admin menyusida "📧 Email import (Excel)" tugmasi bosiganda ishga tushadi.

Qo'llab-quvvatlanadigan Excel formatlari:
  FORMAT A (sarlavhali):
    Kod | Email | Ota-ona Email
    SS1001 | ali@gmail.com | otasi@mail.ru

  FORMAT B (sarlavhasiz, faqat 2 ustun):
    SS1001 | ali@gmail.com

  FORMAT C (sarlavhasiz, 3 ustun):
    SS1001 | ali@gmail.com | otasi@mail.ru

Integratsiya (bot.py yoki admin.py ga qo'shing):
    import email_import
    dp.include_router(email_import.router)

keyboards.py → admin_menu_keyboard() ga qo'shing:
    [KeyboardButton(text="📧 Email import (Excel)")],
"""

import io
import re
import logging
import os

import pandas as pd
from aiogram import Router, F
from aiogram.types import Message, Document, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

logger = logging.getLogger(__name__)
router = Router()

# ─── Email validatsiya ────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$")


def _valid_email(val) -> str | None:
    """Emailni tekshiradi va tozalangan holda qaytaradi, aks holda None."""
    if not val or str(val).strip() in ("", "nan", "None", "-", "—"):
        return None
    cleaned = str(val).strip().lower()
    return cleaned if EMAIL_RE.match(cleaned) else None


# ─── FSM holatlari ────────────────────────────────────────────────────────────

class EmailImport(StatesGroup):
    fayl_kutish = State()


# ─── Admin tekshirish ─────────────────────────────────────────────────────────

async def _admin_tekshir(state: FSMContext, user_id: int) -> bool:
    from config import ADMIN_IDS
    data = await state.get_data()
    return data.get("admin_logged_in") or user_id in ADMIN_IDS


# ─── Shablon Excel generatsiya ────────────────────────────────────────────────

def _shablon_yaratish() -> bytes:
    """
    Admin yuklab olishi uchun namuna Excel fayl yaratadi.
    Sarlavhalar va 3 ta namuna qator bilan.
    """
    df = pd.DataFrame([
        {"Kod": "SS1001", "Email": "ali@gmail.com",     "Ota-ona Email": "otasi@mail.ru"},
        {"Kod": "SS1002", "Email": "zulfiya@mail.ru",   "Ota-ona Email": ""},
        {"Kod": "SS1003", "Email": "",                  "Ota-ona Email": "onasi@gmail.com"},
    ])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Emaillar")

        # Ustun kengligini moslash
        ws = writer.sheets["Emaillar"]
        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 28
        ws.column_dimensions["C"].width = 28

    return buf.getvalue()


# ─── 1-qadam: Tugma bosildi → shablon + fayl so'rash ────────────────────────

@router.message(F.text == "📧 Email import (Excel)")
async def email_import_start(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        await message.answer("⛔ Ruxsat yo'q.")
        return

    shablon_bytes = _shablon_yaratish()
    shablon_file = BufferedInputFile(
        shablon_bytes,
        filename="email_import_shablon.xlsx"
    )

    await message.answer_document(
        document=shablon_file,
        caption=(
            "📧 <b>Email import — shablon fayl</b>\n\n"
            "Yuqoridagi faylni yuklab oling, to'ldiring va qayta yuboring.\n\n"
            "<b>Ustunlar:</b>\n"
            "• <b>Kod</b> — o'quvchi kodi (masalan: SS1001)\n"
            "• <b>Email</b> — o'quvchining o'z emaili (ixtiyoriy)\n"
            "• <b>Ota-ona Email</b> — ota-ona emaili (ixtiyoriy)\n\n"
            "⚠️ Har bir qatorda kamida bitta email bo'lishi kerak.\n"
            "📌 Fayl <b>.xlsx</b> yoki <b>.xls</b> formatida bo'lsin."
        ),
        parse_mode="HTML",
    )

    await state.set_state(EmailImport.fayl_kutish)
    await message.answer("📎 Endi to'ldirilgan Excel faylni yuboring:")


# ─── 2-qadam: Fayl qabul → import ────────────────────────────────────────────

@router.message(EmailImport.fayl_kutish, F.document)
async def email_import_process(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return

    doc: Document = message.document
    if not doc.file_name or not doc.file_name.lower().endswith((".xlsx", ".xls")):
        await message.answer(
            "❌ Fayl turi noto'g'ri. Faqat <b>.xlsx</b> yoki <b>.xls</b> yuboring.",
            parse_mode="HTML",
        )
        return

    # Faylni yuklab olish
    tmp_path = f"email_import_{message.from_user.id}.xlsx"
    file = await message.bot.get_file(doc.file_id)
    await message.bot.download_file(file.file_path, tmp_path)

    await message.answer("⏳ Fayl tahlil qilinmoqda...")

    try:
        df = pd.read_excel(tmp_path, dtype=str)
    except Exception as e:
        await message.answer(f"❌ Faylni o'qishda xato: {e}")
        _cleanup(tmp_path)
        await state.clear()
        return
    finally:
        _cleanup(tmp_path)

    if df.empty:
        await message.answer("❌ Fayl bo'sh.")
        await state.clear()
        return

    # ── Ustun xaritalash ──────────────────────────────────────────────────────
    cols = [str(c).strip() for c in df.columns]
    norm = [c.lower().replace(" ", "").replace("-", "").replace("'", "").replace("'", "") for c in cols]

    def find(keywords: list[str]) -> int | None:
        for kw in keywords:
            for i, n in enumerate(norm):
                if kw in n:
                    return i
        return None

    i_kod    = find(["kod", "code", "id"])
    i_email  = find(["email", "mail", "pochta"])
    i_parent = find(["otaona", "parent", "ota", "ona"])

    # Sarlavhasiz format — pozitsiya bo'yicha
    if i_kod is None:
        if len(df.columns) >= 2:
            i_kod, i_email = 0, 1
            i_parent = 2 if len(df.columns) >= 3 else None
        else:
            await message.answer(
                "❌ Fayl formatini aniqlab bo'lmadi.\n"
                "Kamida 2 ta ustun bo'lishi kerak: <b>Kod</b> va <b>Email</b>.",
                parse_mode="HTML",
            )
            await state.clear()
            return

    # ── Qatorlarni qayta ishlash ──────────────────────────────────────────────
    ok = 0          # muvaffaqiyatli yangilangan
    skip_empty = 0  # email ham, parent_email ham bo'sh
    skip_notfound = 0  # kod bazada topilmadi
    skip_invalid = 0   # email formati noto'g'ri
    errors = []

    from database import get_connection, release_connection

    for idx, row in df.iterrows():
        lineno = idx + 2  # Excel qator raqami (sarlavha = 1)

        kod_raw = str(row.iloc[i_kod]).strip().upper()
        if not kod_raw or kod_raw in ("NAN", "NONE", ""):
            continue

        email_raw   = row.iloc[i_email] if i_email is not None else None
        parent_raw  = row.iloc[i_parent] if i_parent is not None else None

        email   = _valid_email(email_raw)
        parent  = _valid_email(parent_raw)

        # Ikkisi ham bo'sh — o'tkazib yuborish
        if not email and not parent:
            skip_empty += 1
            continue

        # Noto'g'ri format bo'lsa log qilamiz (lekin davom etamiz)
        if email_raw and str(email_raw).strip() not in ("", "nan", "None") and not email:
            errors.append(f"Qator {lineno}: '{email_raw}' — noto'g'ri email format")
            skip_invalid += 1

        if parent_raw and str(parent_raw).strip() not in ("", "nan", "None") and not parent:
            errors.append(f"Qator {lineno}: '{parent_raw}' — noto'g'ri ota-ona email format")
            skip_invalid += 1

        if not email and not parent:
            continue

        # Bazaga yozish
        try:
            conn = get_connection()
            cur = conn.cursor()

            # Avval student bor-yo'qligini tekshiramiz
            cur.execute("SELECT kod FROM talabalar WHERE kod = %s", (kod_raw,))
            if not cur.fetchone():
                skip_notfound += 1
                cur.close()
                release_connection(conn)
                continue

            # Faqat berilgan maydonlarni yangilash
            updates = []
            params = []
            if email:
                updates.append("email = %s")
                params.append(email)
            if parent:
                updates.append("parent_email = %s")
                params.append(parent)

            params.append(kod_raw)
            cur.execute(
                f"UPDATE talabalar SET {', '.join(updates)} WHERE kod = %s",
                params,
            )
            conn.commit()
            cur.close()
            release_connection(conn)
            ok += 1

        except Exception as e:
            errors.append(f"Qator {lineno} ({kod_raw}): DB xato — {e}")
            try:
                release_connection(conn)
            except Exception:
                pass

    # ── Natija xabari ─────────────────────────────────────────────────────────
    lines = [
        "📧 <b>Email import yakunlandi!</b>\n",
        f"✅ Muvaffaqiyatli yangilandi: <b>{ok} ta</b>",
        f"⚠️ Email bo'sh qatorlar o'tkazib yuborildi: <b>{skip_empty} ta</b>",
        f"🔍 Kod topilmadi: <b>{skip_notfound} ta</b>",
        f"❌ Noto'g'ri email format: <b>{skip_invalid} ta</b>",
    ]

    if errors:
        lines.append(f"\n<b>Xatolar ({min(len(errors), 10)} ta ko'rsatildi):</b>")
        for err in errors[:10]:
            lines.append(f"  • {err}")
        if len(errors) > 10:
            lines.append(f"  ... va yana {len(errors) - 10} ta xato")

    if ok == 0 and skip_notfound > 0:
        lines.append(
            "\n💡 <b>Eslatma:</b> Kodlar topilmadi. "
            "Bazada <code>email</code> ustunlari yo'q bo'lishi mumkin — "
            "avval migration ni ishga tushiring."
        )

    await message.answer("\n".join(lines), parse_mode="HTML")
    await state.clear()


# ─── Noto'g'ri fayl turi ─────────────────────────────────────────────────────

@router.message(EmailImport.fayl_kutish)
async def email_import_wrong_file(message: Message, state: FSMContext):
    await message.answer(
        "📎 Iltimos, faqat <b>.xlsx</b> yoki <b>.xls</b> formatidagi faylni yuboring.\n"
        "Yoki /cancel deb yozing.",
        parse_mode="HTML",
    )


# ─── Yordamchi ───────────────────────────────────────────────────────────────

def _cleanup(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
