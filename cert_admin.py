"""
cert_admin.py — Sertifikat sozlamalari admin paneli.

Funksiyalar:
  • Sarlavha, subtitle, maktab nomi, matn o'zgartirish
  • Rang (R,G,B) sozlash  — oldindan tayyorlangan ranglar + custom
  • Logo yuklash (rasm) yoki o'chirish
  • Ko'rinish: "Sertifikat ko'rinishi" — preview PDF generatsiya

Integratsiya:
  1. bot.py   → dp.include_router(cert_admin.router)  qo'shing
  2. admin.py → "📜 Sertifikat" tugmasini sozlamalar menyusiga qo'shing
"""
from __future__ import annotations

import asyncio
import os
import io

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_setting, set_setting
from certificate import CertificateGenerator, CERT_DEFAULTS

router = Router()

# ── FSM holatlari ─────────────────────────────────────────────────────────────

class CertSozlama(StatesGroup):
    sarlavha_kutish    = State()
    subtitle_kutish    = State()
    maktab_kutish      = State()
    matn_kutish        = State()
    rang_r_kutish      = State()
    rang_g_kutish      = State()
    rang_b_kutish      = State()
    logo_kutish        = State()

# ── Oldindan tayyorlangan ranglar ─────────────────────────────────────────────

RANGLAR = {
    "🔵 Ko'k":        (0,   0,   128),
    "🟤 Qo'ng'ir":    (101, 67,  33 ),
    "🟢 Yashil":      (0,   100, 0  ),
    "🔴 Qizil":       (139, 0,   0  ),
    "🟣 Binafsha":    (75,  0,   130),
    "⬛ Qora":        (0,   0,   0  ),
    "🩵 Moviy":       (0,   119, 182),
    "🟠 To'q sariq":  (180, 100, 0  ),
}

# ── Yordamchi funksiyalar ─────────────────────────────────────────────────────

async def _admin_tekshir(state: FSMContext, user_id: int) -> bool:
    """admin_tekshir ni cert_admin'dan chaqirish uchun."""
    data = await state.get_data()
    if data.get("admin") is True:
        return True
    try:
        from config import ADMIN_IDS
        if int(user_id) in [int(i) for i in ADMIN_IDS]:
            await state.update_data(admin=True)
            return True
    except Exception:
        pass
    return False


def _get_all_settings() -> dict[str, str]:
    return {
        key: get_setting(key, default)
        for key, default in CERT_DEFAULTS.items()
    }


def _rang_text(r: str, g: str, b: str) -> str:
    return f"RGB({r}, {g}, {b})"


def _menu_text(s: dict) -> str:
    return (
        "📜 <b>Sertifikat sozlamalari</b>\n\n"
        f"🔤 <b>Sarlavha:</b> {s['cert_sarlavha']}\n"
        f"📝 <b>Subtitle:</b> {s['cert_subtitle']}\n"
        f"🏫 <b>Maktab nomi:</b> {s['cert_maktab_nomi']}\n"
        f"📄 <b>Matn:</b> {s['cert_matn']}\n"
        f"🎨 <b>Rang:</b> {_rang_text(s['cert_rang_r'], s['cert_rang_g'], s['cert_rang_b'])}\n"
        f"🖼 <b>Logo:</b> {('✅ Yuklangan' if s.get('cert_logo_path') and os.path.exists(s['cert_logo_path']) else chr(10060)+' Yo'+chr(39)+'q')}\n\n"
        "O'zgartirmoqchi bo'lgan bo'limni tanlang:"
    )


def _menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔤 Sarlavha",     callback_data="cert_edit:sarlavha")],
        [InlineKeyboardButton(text="📝 Subtitle",     callback_data="cert_edit:subtitle")],
        [InlineKeyboardButton(text="🏫 Maktab nomi",  callback_data="cert_edit:maktab")],
        [InlineKeyboardButton(text="📄 Qo'shimcha matn", callback_data="cert_edit:matn")],
        [InlineKeyboardButton(text="🎨 Rang",         callback_data="cert_edit:rang")],
        [InlineKeyboardButton(text="🖼 Logo",         callback_data="cert_edit:logo")],
        [InlineKeyboardButton(text="👁 Ko'rinish (Preview)", callback_data="cert_preview")],
        [InlineKeyboardButton(text="🔄 Defaults",    callback_data="cert_reset")],
    ])


def _rang_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=nom, callback_data=f"cert_rang:{r}:{g}:{b}")]
        for nom, (r, g, b) in RANGLAR.items()
    ]
    buttons.append([InlineKeyboardButton(text="✏️ Custom RGB", callback_data="cert_rang:custom")])
    buttons.append([InlineKeyboardButton(text="◀️ Orqaga",      callback_data="cert_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _logo_keyboard(has_logo: bool) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📤 Rasm yuklash", callback_data="cert_logo:upload")],
    ]
    if has_logo:
        rows.append([InlineKeyboardButton(text="🗑 Logoni o'chirish", callback_data="cert_logo:delete")])
    rows.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="cert_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ── Bosh menyu ────────────────────────────────────────────────────────────────

@router.message(F.text == "📜 Sertifikat sozlamalari")
async def cert_menu_message(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return
    s = _get_all_settings()
    await message.answer(_menu_text(s), parse_mode="HTML", reply_markup=_menu_keyboard())


@router.callback_query(F.data == "cert_menu")
async def cert_menu_cb(cb: CallbackQuery, state: FSMContext):
    if not await _admin_tekshir(state, cb.from_user.id):
        return
    s = _get_all_settings()
    await cb.message.edit_text(_menu_text(s), parse_mode="HTML", reply_markup=_menu_keyboard())
    await cb.answer()

# ── Matn tahrirlash ───────────────────────────────────────────────────────────

_EDIT_META = {
    "sarlavha": ("cert_sarlavha",    "sarlavha_kutish",  "📜 SERTIFIKAT sarlavhasini kiriting:\n\nMisol: <code>SERTIFIKAT</code>"),
    "subtitle": ("cert_subtitle",    "subtitle_kutish",  "📝 Subtitle matnini kiriting:\n\nMisol: <code>O'quvchining ismi va familyasi</code>"),
    "maktab":   ("cert_maktab_nomi", "maktab_kutish",    "🏫 Maktab nomini kiriting:\n\nMisol: <code>Bo'stonliq tumani ixtisoslashtirilgan maktabining</code>"),
    "matn":     ("cert_matn",        "matn_kutish",      "📄 Qo'shimcha matn kiriting:\n\nMisol: <code>DTM imtihonida olingan ball</code>"),
}

@router.callback_query(F.data.startswith("cert_edit:"))
async def cert_edit_start(cb: CallbackQuery, state: FSMContext):
    if not await _admin_tekshir(state, cb.from_user.id):
        return
    field = cb.data.split(":")[1]

    if field == "rang":
        await cb.message.edit_text(
            "🎨 <b>Rang tanlang:</b>\n\nSertifikat chegara va sarlavha rangi:",
            parse_mode="HTML",
            reply_markup=_rang_keyboard(),
        )
        await cb.answer()
        return

    if field == "logo":
        s = _get_all_settings()
        has_logo = bool(s.get("cert_logo_path") and os.path.exists(s["cert_logo_path"]))
        await cb.message.edit_text(
            "🖼 <b>Logo sozlamalari:</b>\n\nLogo sertifikat sarlavhasi ustida, markazda joylashadi (25×25 mm).",
            parse_mode="HTML",
            reply_markup=_logo_keyboard(has_logo),
        )
        await cb.answer()
        return

    if field not in _EDIT_META:
        await cb.answer("Noma'lum bo'lim")
        return

    db_key, state_name, prompt = _EDIT_META[field]
    current_val = get_setting(db_key, CERT_DEFAULTS[db_key])
    await state.update_data(_cert_edit_key=db_key)
    target_state = getattr(CertSozlama, state_name)
    await state.set_state(target_state)
    await cb.message.edit_text(
        f"{prompt}\n\n<i>Joriy qiymat:</i> <code>{current_val}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cert_menu")]
        ]),
    )
    await cb.answer()


@router.message(CertSozlama.sarlavha_kutish)
@router.message(CertSozlama.subtitle_kutish)
@router.message(CertSozlama.maktab_kutish)
@router.message(CertSozlama.matn_kutish)
async def cert_text_received(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return
    data = await state.get_data()
    db_key = data.get("_cert_edit_key")
    if not db_key:
        await state.clear()
        return

    new_val = (message.text or "").strip()
    if not new_val:
        await message.answer("⚠️ Bo'sh qiymat saqlanmaydi. Qayta kiriting yoki /cancel yozing.")
        return

    set_setting(db_key, new_val)
    await state.clear()

    s = _get_all_settings()
    await message.answer(
        f"✅ Saqlandi!\n\n" + _menu_text(s),
        parse_mode="HTML",
        reply_markup=_menu_keyboard(),
    )

# ── Rang tanlash ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("cert_rang:"))
async def cert_rang_select(cb: CallbackQuery, state: FSMContext):
    if not await _admin_tekshir(state, cb.from_user.id):
        return
    parts = cb.data.split(":")

    if parts[1] == "custom":
        await state.set_state(CertSozlama.rang_r_kutish)
        await cb.message.edit_text(
            "🎨 <b>Custom rang — R qiymatini kiriting (0–255):</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Bekor", callback_data="cert_menu")]
            ]),
        )
        await cb.answer()
        return

    # Oldindan tayyorlangan rang: cert_rang:R:G:B
    try:
        r, g, b = int(parts[1]), int(parts[2]), int(parts[3])
    except (IndexError, ValueError):
        await cb.answer("Xato")
        return

    set_setting("cert_rang_r", str(r))
    set_setting("cert_rang_g", str(g))
    set_setting("cert_rang_b", str(b))

    s = _get_all_settings()
    await cb.message.edit_text(
        f"✅ Rang saqlandi: RGB({r}, {g}, {b})\n\n" + _menu_text(s),
        parse_mode="HTML",
        reply_markup=_menu_keyboard(),
    )
    await cb.answer()


@router.message(CertSozlama.rang_r_kutish)
async def rang_r_received(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return
    try:
        r = max(0, min(255, int(message.text.strip())))
    except ValueError:
        await message.answer("⚠️ 0 dan 255 gacha raqam kiriting:")
        return
    await state.update_data(_cert_r=r)
    await state.set_state(CertSozlama.rang_g_kutish)
    await message.answer(f"✅ R={r}\n\n🎨 <b>G qiymatini kiriting (0–255):</b>", parse_mode="HTML")


@router.message(CertSozlama.rang_g_kutish)
async def rang_g_received(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return
    try:
        g = max(0, min(255, int(message.text.strip())))
    except ValueError:
        await message.answer("⚠️ 0 dan 255 gacha raqam kiriting:")
        return
    await state.update_data(_cert_g=g)
    await state.set_state(CertSozlama.rang_b_kutish)
    await message.answer(f"✅ G={g}\n\n🎨 <b>B qiymatini kiriting (0–255):</b>", parse_mode="HTML")


@router.message(CertSozlama.rang_b_kutish)
async def rang_b_received(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return
    try:
        b = max(0, min(255, int(message.text.strip())))
    except ValueError:
        await message.answer("⚠️ 0 dan 255 gacha raqam kiriting:")
        return
    data = await state.get_data()
    r = data.get("_cert_r", 0)
    g = data.get("_cert_g", 0)
    set_setting("cert_rang_r", str(r))
    set_setting("cert_rang_g", str(g))
    set_setting("cert_rang_b", str(b))
    await state.clear()

    s = _get_all_settings()
    await message.answer(
        f"✅ Rang saqlandi: RGB({r}, {g}, {b})\n\n" + _menu_text(s),
        parse_mode="HTML",
        reply_markup=_menu_keyboard(),
    )

# ── Logo ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "cert_logo:upload")
async def cert_logo_upload_start(cb: CallbackQuery, state: FSMContext):
    if not await _admin_tekshir(state, cb.from_user.id):
        return
    await state.set_state(CertSozlama.logo_kutish)
    await cb.message.edit_text(
        "🖼 <b>Logo rasmini yuboring:</b>\n\n"
        "• PNG yoki JPG formatida\n"
        "• Iloji boricha kvadrat (masalan 200×200 px)\n"
        "• Fondi oq yoki shaffof bo'lsa yaxshi\n\n"
        "⚠️ <b>Shaffof (transparent) fon uchun:</b>\n"
        "Rasmni 📎 <b>Fayl sifatida</b> yuboring — aks holda Telegram\n"
        "transparency ni yo'qotib, qora fon hosil qiladi.\n\n"
        "<i>Oddiy fon uchun rasm sifatida yuborish ham mumkin.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor", callback_data="cert_menu")]
        ]),
    )
    await cb.answer()


def _save_logo_as_png(raw_bytes: bytes, logo_path: str) -> str:
    """
    Rasmni PNG formatida saqlaydi.
    Transparent (RGBA) fon saqlanadi — FPDF uchun RGB ga o'tkazilmaydi,
    chunki fpdf2 PNG transparency ni to'g'ri handle qiladi.
    Agar Pillow mavjud bo'lmasa, xom baytlarni to'g'ridan-to'g'ri yozadi.
    """
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(raw_bytes))
        # RGBA yoki P (palette + transparency) ni to'g'ridan-to'g'ri saqlash
        # fpdf2 PNG transparency ni qo'llab-quvvatlaydi
        if img.mode not in ("RGBA", "RGB", "L", "LA"):
            img = img.convert("RGBA")
        img.save(logo_path, format="PNG")
    except ImportError:
        # Pillow yo'q — xom baytlarni yoz (agar original PNG bo'lsa)
        with open(logo_path, "wb") as f:
            f.write(raw_bytes)
    return logo_path


@router.message(CertSozlama.logo_kutish, F.photo)
async def cert_logo_received(message: Message, state: FSMContext, bot: Bot):
    """Rasm sifatida yuborilganda (Telegram JPEG ga o'zgartiradi, transparency yo'qoladi)."""
    if not await _admin_tekshir(state, message.from_user.id):
        return

    logo_dir = "cert_assets"
    os.makedirs(logo_dir, exist_ok=True)
    logo_path = os.path.join(logo_dir, "cert_logo.png")

    # Eng katta o'lchamdagi rasmni olish
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)

    import io
    buf = io.BytesIO()
    await bot.download_file(file.file_path, destination=buf)
    _save_logo_as_png(buf.getvalue(), logo_path)

    set_setting("cert_logo_path", logo_path)
    await state.clear()

    s = _get_all_settings()
    await message.answer(
        "✅ Logo yuklandi va saqlandi!\n\n"
        "⚠️ <i>Eslatma: Shaffof (transparent) logoni saqlash uchun rasmni "
        "<b>fayl sifatida</b> yuboring (📎 → Fayl), chunki Telegram oddiy "
        "rasm yuborganda transparency ni yo'qotadi.</i>\n\n" + _menu_text(s),
        parse_mode="HTML",
        reply_markup=_menu_keyboard(),
    )


@router.message(CertSozlama.logo_kutish, F.document)
async def cert_logo_received_as_file(message: Message, state: FSMContext, bot: Bot):
    """Fayl sifatida yuborilganda — PNG transparency to'liq saqlanadi."""
    if not await _admin_tekshir(state, message.from_user.id):
        return

    doc = message.document
    mime = doc.mime_type or ""
    if mime not in ("image/png", "image/jpeg", "image/jpg", "image/webp") and \
       not (doc.file_name or "").lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        await message.answer(
            "⚠️ Faqat PNG, JPG yoki WEBP formatidagi rasm fayli yuboring.\n"
            "Yoki /cancel yozing.",
            parse_mode="HTML",
        )
        return

    logo_dir = "cert_assets"
    os.makedirs(logo_dir, exist_ok=True)
    logo_path = os.path.join(logo_dir, "cert_logo.png")

    import io
    file = await bot.get_file(doc.file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, destination=buf)
    _save_logo_as_png(buf.getvalue(), logo_path)

    set_setting("cert_logo_path", logo_path)
    await state.clear()

    s = _get_all_settings()
    await message.answer(
        "✅ Logo (fayl) yuklandi va saqlandi! Transparency saqlanadi.\n\n" + _menu_text(s),
        parse_mode="HTML",
        reply_markup=_menu_keyboard(),
    )


@router.message(CertSozlama.logo_kutish)
async def cert_logo_wrong_type(message: Message, state: FSMContext):
    await message.answer(
        "⚠️ Iltimos <b>rasm</b> yuboring.\n"
        "• Shaffof (transparent) fon uchun: 📎 <b>Fayl sifatida</b> yuboring\n"
        "• Oddiy fon uchun: Rasm sifatida yuboring\n"
        "Yoki /cancel yozing.",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "cert_logo:delete")
async def cert_logo_delete(cb: CallbackQuery, state: FSMContext):
    if not await _admin_tekshir(state, cb.from_user.id):
        return
    logo_path = get_setting("cert_logo_path", "")
    if logo_path and os.path.exists(logo_path):
        try:
            os.remove(logo_path)
        except OSError:
            pass
    set_setting("cert_logo_path", "")

    s = _get_all_settings()
    await cb.message.edit_text(
        "✅ Logo o'chirildi.\n\n" + _menu_text(s),
        parse_mode="HTML",
        reply_markup=_menu_keyboard(),
    )
    await cb.answer()

# ── Preview ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "cert_preview")
async def cert_preview(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if not await _admin_tekshir(state, cb.from_user.id):
        return
    await cb.answer("⏳ Generatsiya qilinmoqda...")
    await cb.message.edit_text("⏳ <b>Preview sertifikat tayyorlanmoqda...</b>", parse_mode="HTML")

    loop = asyncio.get_event_loop()
    try:
        gen = CertificateGenerator.from_db()
        path = await loop.run_in_executor(
            None,
            gen.generate,
            "Sultanov Diyorbek Alibek o'g'li",
            189.6,
            "2025-06-01",
            "PREVIEW",
            "11-A",
            "Bo'stonliq ITMA",
        )
        await bot.send_document(
            cb.from_user.id,
            FSInputFile(path),
            caption=(
                "👁 <b>Sertifikat ko'rinishi (preview)</b>\n\n"
                "Bu namuna sertifikat. Haqiqiy o'quvchi ma'lumotlari bilan ham xuddi shunday ko'rinadi."
            ),
            parse_mode="HTML",
        )
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        await bot.send_message(cb.from_user.id, f"❌ Preview xatosi: {e}")

    s = _get_all_settings()
    await cb.message.edit_text(_menu_text(s), parse_mode="HTML", reply_markup=_menu_keyboard())

# ── Default'ga qaytarish ──────────────────────────────────────────────────────

@router.callback_query(F.data == "cert_reset")
async def cert_reset(cb: CallbackQuery, state: FSMContext):
    if not await _admin_tekshir(state, cb.from_user.id):
        return
    await cb.message.edit_text(
        "⚠️ <b>Barcha sertifikat sozlamalarini default'ga qaytarishni xohlaysizmi?</b>\n\n"
        "Bu amalni qaytarib bo'lmaydi.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha, qaytarish", callback_data="cert_reset:confirm"),
                InlineKeyboardButton(text="❌ Yo'q",          callback_data="cert_menu"),
            ]
        ]),
    )
    await cb.answer()


@router.callback_query(F.data == "cert_reset:confirm")
async def cert_reset_confirm(cb: CallbackQuery, state: FSMContext):
    if not await _admin_tekshir(state, cb.from_user.id):
        return
    for key, val in CERT_DEFAULTS.items():
        set_setting(key, val)
    s = _get_all_settings()
    await cb.message.edit_text(
        "✅ Default sozlamalar tiklandi.\n\n" + _menu_text(s),
        parse_mode="HTML",
        reply_markup=_menu_keyboard(),
    )
    await cb.answer()
