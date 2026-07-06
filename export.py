"""
routers/export.py
-----------------
Telegram bot uchun "Arxiv va Eksport" routeri.
Registratsiya: dp.include_router(export_router)
"""

import asyncio
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.export_service import (
    fetch_student_data,
    build_zip_archive,
)

logger = logging.getLogger(__name__)
export_router = Router(name="export")


# ─────────────────────────────────────────────────
#  Klaviatura
# ─────────────────────────────────────────────────

def export_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 ZIP arxiv (PDF + Excel)", callback_data="export_zip")
    builder.button(text="📊 Faqat Excel",             callback_data="export_excel")
    builder.button(text="📄 Faqat PDF (oxirgi mock)", callback_data="export_last_pdf")
    builder.button(text="❌ Bekor qilish",            callback_data="export_cancel")
    builder.adjust(1)
    return builder.as_markup()


# ─────────────────────────────────────────────────
#  Handlerlar
# ─────────────────────────────────────────────────

@export_router.message(Command("arxiv"))
@export_router.message(F.text.in_({"📦 Arxiv", "Arxiv va eksport", "📥 Natijalarni yuklab olish"}))
async def cmd_export_menu(message: Message):
    """Eksport menyusini ko'rsatadi."""
    await message.answer(
        "📦 <b>Arxiv va Eksport markazi</b>\n\n"
        "Barcha natijalaringizni qulay formatda yuklab olishingiz mumkin:\n\n"
        "• <b>ZIP</b> — PDF hisobotlar + Excel jadval (hammasi)\n"
        "• <b>Excel</b> — faqat jadval (mock + mini-testlar)\n"
        "• <b>PDF</b> — faqat oxirgi mock natijasi\n\n"
        "Qaysi formatni tanlaysiz?",
        parse_mode="HTML",
        reply_markup=export_menu_kb(),
    )


# ── ZIP ───────────────────────────────────────────

@export_router.callback_query(F.data == "export_zip")
async def cb_export_zip(callback: CallbackQuery, db_pool):
    await callback.answer()
    status_msg = await callback.message.answer(
        "⏳ ZIP arxiv tayyorlanmoqda...\n"
        "Bu bir necha soniya olishi mumkin."
    )

    try:
        data = await fetch_student_data(db_pool, callback.from_user.id)
        if not data:
            await status_msg.edit_text("❌ Sizning ma'lumotlaringiz topilmadi.")
            return

        if not data["mock_results"] and not data["mini_results"]:
            await status_msg.edit_text(
                "📭 Hali hech qanday natija yo'q.\n"
                "Avval biror test ishlab ko'ring!"
            )
            return

        # Arxivni hosil qilish (bloklovchi kodni executor da ishlat)
        loop     = asyncio.get_event_loop()
        zip_buf  = await loop.run_in_executor(None, build_zip_archive, data)

        safe_name = (data["student"].get("full_name") or "student").replace(" ", "_")
        filename  = f"{safe_name}_arxiv.zip"

        await callback.message.answer_document(
            document=BufferedInputFile(zip_buf.read(), filename=filename),
            caption=(
                f"✅ <b>Arxiv tayyor!</b>\n\n"
                f"📊 Mock natijalari: <b>{len(data['mock_results'])} ta</b>\n"
                f"📝 Mini-testlar:     <b>{len(data['mini_results'])} ta</b>\n\n"
                f"Arxiv tarkibi:\n"
                f"  • <code>{safe_name}_natijalar.xlsx</code>\n"
                f"  • <code>pdf/</code> — har bir mock uchun hisobot"
            ),
            parse_mode="HTML",
        )
        await status_msg.delete()

    except Exception as e:
        logger.exception("ZIP arxiv xatosi: %s", e)
        await status_msg.edit_text(
            "⚠️ Arxiv yaratishda xato yuz berdi.\n"
            "Iltimos qayta urinib ko'ring yoki @admin ga xabar bering."
        )


# ── Excel ─────────────────────────────────────────

@export_router.callback_query(F.data == "export_excel")
async def cb_export_excel(callback: CallbackQuery, db_pool):
    await callback.answer()
    status_msg = await callback.message.answer("⏳ Excel tayyorlanmoqda...")

    try:
        from services.export_service import generate_excel, fetch_student_data
        import asyncio

        data = await fetch_student_data(db_pool, callback.from_user.id)
        if not data:
            await status_msg.edit_text("❌ Ma'lumotlar topilmadi.")
            return

        loop        = asyncio.get_event_loop()
        excel_bytes = await loop.run_in_executor(None, generate_excel, data)

        safe_name = (data["student"].get("full_name") or "student").replace(" ", "_")
        filename  = f"{safe_name}_natijalar.xlsx"

        await callback.message.answer_document(
            document=BufferedInputFile(excel_bytes, filename=filename),
            caption=(
                f"📊 <b>Excel jadval tayyor!</b>\n\n"
                f"Varaqlar:\n"
                f"  1️⃣ Mock natijalari ({len(data['mock_results'])} qator)\n"
                f"  2️⃣ Mini-testlar ({len(data['mini_results'])} qator)\n"
                f"  3️⃣ Profil ma'lumotlari"
            ),
            parse_mode="HTML",
        )
        await status_msg.delete()

    except Exception as e:
        logger.exception("Excel xatosi: %s", e)
        await status_msg.edit_text("⚠️ Xato yuz berdi. Qayta urinib ko'ring.")


# ── PDF (oxirgi mock) ─────────────────────────────

@export_router.callback_query(F.data == "export_last_pdf")
async def cb_export_last_pdf(callback: CallbackQuery, db_pool):
    await callback.answer()
    status_msg = await callback.message.answer("⏳ PDF hisobot tayyorlanmoqda...")

    try:
        from services.export_service import generate_mock_pdf, fetch_student_data
        import asyncio

        data = await fetch_student_data(db_pool, callback.from_user.id)
        if not data or not data["mock_results"]:
            await status_msg.edit_text("❌ Hali mock imtihon natijasi yo'q.")
            return

        last_mock = data["mock_results"][0]  # DESC tartib, birinchisi eng oxirgi

        loop      = asyncio.get_event_loop()
        pdf_bytes = await loop.run_in_executor(
            None, generate_mock_pdf, last_mock, data["student"]
        )

        exam_type = last_mock.get("exam_type", "mock").replace(" ", "_")
        filename  = f"{exam_type}_natija.pdf"

        await callback.message.answer_document(
            document=BufferedInputFile(pdf_bytes, filename=filename),
            caption=(
                f"📄 <b>{last_mock.get('exam_type', 'Mock')} — oxirgi natija</b>\n\n"
                f"🏆 Ball: <b>{last_mock.get('band_score') or last_mock.get('total_score')}</b>\n"
                + (f"🔑 Sertifikat: <code>{last_mock['certificate_code']}</code>"
                   if last_mock.get("certificate_code") else "")
            ),
            parse_mode="HTML",
        )
        await status_msg.delete()

    except Exception as e:
        logger.exception("PDF xatosi: %s", e)
        await status_msg.edit_text("⚠️ Xato yuz berdi. Qayta urinib ko'ring.")


# ── Bekor qilish ──────────────────────────────────

@export_router.callback_query(F.data == "export_cancel")
async def cb_export_cancel(callback: CallbackQuery):
    await callback.answer("Bekor qilindi")
    await callback.message.delete()
