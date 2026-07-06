"""
export.py
---------
Telegram bot uchun "Arxiv va Eksport" routeri.
Registratsiya: dp.include_router(export_router)

O'quvchi uchun: ZIP / Excel / oxirgi mock PDF yuklab olish.
Admin uchun:   istalgan o'quvchining arxivini kod bo'yicha yuklab olish
               (talaba_tahrirlash bo'limidagi "📦 Natijalar arxivi" tugmasi).
"""

import asyncio
import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database import get_setting
from export_service import (
    fetch_student_data,
    fetch_student_data_by_kod,
    generate_excel,
    build_zip_archive,
)
from mock_report import generate_mock_report

logger = logging.getLogger(__name__)
export_router = Router(name="export")


# ─────────────────────────────────────────────────
#  Yordamchi: admin tekshiruvi (admin.py ga bog'liq bo'lmasligi uchun)
# ─────────────────────────────────────────────────

async def _admin_tekshir(state: FSMContext, user_id: int) -> bool:
    """admin_tekshir ni export.py'dan chaqirish uchun (admin.py'dagi bilan bir xil)."""
    data = await state.get_data()
    if data.get("admin") is True:
        return True
    try:
        from config import ADMIN_IDS
        if int(user_id) in [int(i) for i in ADMIN_IDS]:
            await state.update_data(admin=True, is_maktab_admin=False)
            return True
    except Exception:
        pass
    try:
        from payment import is_maktab_admin, is_subscription_active
        if is_maktab_admin(user_id) and is_subscription_active(user_id):
            await state.update_data(admin=True, is_maktab_admin=True)
            return True
    except Exception:
        pass
    return False


# ─────────────────────────────────────────────────
#  Klaviatura
# ─────────────────────────────────────────────────

def export_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 ZIP arxiv (PDF + Excel)", callback_data="export_zip")
    builder.button(text="📊 Faqat Excel", callback_data="export_excel")
    builder.button(text="📄 Faqat PDF (oxirgi mock)", callback_data="export_last_pdf")
    builder.button(text="❌ Bekor qilish", callback_data="export_cancel")
    builder.adjust(1)
    return builder.as_markup()


# ─────────────────────────────────────────────────
#  O'quvchi uchun handlerlar
# ─────────────────────────────────────────────────

@export_router.message(Command("arxiv"))
@export_router.message(F.text.in_({"📦 Arxiv", "Arxiv va eksport", "📥 Natijalarni yuklab olish"}))
async def cmd_export_menu(message: Message):
    """Eksport menyusini ko'rsatadi."""
    if get_setting("export_enabled", "True") != "True":
        await message.answer("⚠️ Bu xususiyat hozircha o'chirilgan.")
        return

    await message.answer(
        "📦 <b>Arxiv va Eksport markazi</b>\n\n"
        "Barcha natijalaringizni qulay formatda yuklab olishingiz mumkin:\n\n"
        "• <b>ZIP</b> — PDF hisobotlar + Excel jadval (hammasi)\n"
        "• <b>Excel</b> — faqat jadval (mock + asosiy DTM + mini-testlar)\n"
        "• <b>PDF</b> — faqat oxirgi mock natijasi\n\n"
        "Qaysi formatni tanlaysiz?",
        parse_mode="HTML",
        reply_markup=export_menu_kb(),
    )


# ── ZIP ───────────────────────────────────────────

@export_router.callback_query(F.data == "export_zip")
async def cb_export_zip(callback: CallbackQuery):
    if get_setting("export_enabled", "True") != "True":
        await callback.answer("⚠️ Bu xususiyat o'chirilgan.", show_alert=True)
        return

    await callback.answer()
    status_msg = await callback.message.answer(
        "⏳ ZIP arxiv tayyorlanmoqda...\nBu bir necha soniya olishi mumkin."
    )

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, fetch_student_data, callback.from_user.id)

        if not data:
            await status_msg.edit_text(
                "❌ Sizning ma'lumotlaringiz topilmadi. Avval ro'yxatdan o'ting."
            )
            return

        if not data["mock_results"] and not data["dtm_results"] and not data["mini_results"]:
            await status_msg.edit_text(
                "📭 Hali hech qanday natija yo'q.\nAvval biror test ishlab ko'ring!"
            )
            return

        zip_buf = await loop.run_in_executor(None, build_zip_archive, data)

        safe_name = (data["student"].get("ismlar") or "talaba").replace(" ", "_")
        filename = f"{safe_name}_arxiv.zip"

        await callback.message.answer_document(
            document=BufferedInputFile(zip_buf.read(), filename=filename),
            caption=(
                f"✅ <b>Arxiv tayyor!</b>\n\n"
                f"📊 Mock natijalari: <b>{len(data['mock_results'])} ta</b>\n"
                f"🎯 Asosiy DTM: <b>{len(data['dtm_results'])} ta</b>\n"
                f"📝 Mini-testlar: <b>{len(data['mini_results'])} ta</b>\n\n"
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
async def cb_export_excel(callback: CallbackQuery):
    if get_setting("export_enabled", "True") != "True":
        await callback.answer("⚠️ Bu xususiyat o'chirilgan.", show_alert=True)
        return

    await callback.answer()
    status_msg = await callback.message.answer("⏳ Excel tayyorlanmoqda...")

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, fetch_student_data, callback.from_user.id)

        if not data:
            await status_msg.edit_text("❌ Ma'lumotlar topilmadi.")
            return

        excel_bytes = await loop.run_in_executor(None, generate_excel, data)

        safe_name = (data["student"].get("ismlar") or "talaba").replace(" ", "_")
        filename = f"{safe_name}_natijalar.xlsx"

        await callback.message.answer_document(
            document=BufferedInputFile(excel_bytes, filename=filename),
            caption=(
                f"📊 <b>Excel jadval tayyor!</b>\n\n"
                f"Varaqlar:\n"
                f"  1️⃣ Mock natijalari ({len(data['mock_results'])} qator)\n"
                f"  2️⃣ Asosiy DTM ({len(data['dtm_results'])} qator)\n"
                f"  3️⃣ Mini-testlar ({len(data['mini_results'])} qator)\n"
                f"  4️⃣ Profil ma'lumotlari"
            ),
            parse_mode="HTML",
        )
        await status_msg.delete()

    except Exception as e:
        logger.exception("Excel xatosi: %s", e)
        await status_msg.edit_text("⚠️ Xato yuz berdi. Qayta urinib ko'ring.")


# ── PDF (oxirgi mock) ─────────────────────────────

@export_router.callback_query(F.data == "export_last_pdf")
async def cb_export_last_pdf(callback: CallbackQuery):
    if get_setting("export_enabled", "True") != "True":
        await callback.answer("⚠️ Bu xususiyat o'chirilgan.", show_alert=True)
        return

    await callback.answer()
    status_msg = await callback.message.answer("⏳ PDF hisobot tayyorlanmoqda...")

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, fetch_student_data, callback.from_user.id)

        if not data or not data["mock_results"]:
            await status_msg.edit_text("❌ Hali mock imtihon natijasi yo'q.")
            return

        last_mock = data["mock_results"][0]  # DESC tartib, birinchisi eng oxirgi
        kod = data["student"]["kod"]

        pdf_path, _png_path = await loop.run_in_executor(
            None, generate_mock_report, kod, None, last_mock.get("id")
        )

        if not pdf_path:
            await status_msg.edit_text("⚠️ PDF hisobotni yaratib bo'lmadi.")
            return

        exam_key = (last_mock.get("exam_key") or "mock").replace(" ", "_")
        filename = f"{exam_key}_natija.pdf"

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        import os
        try:
            os.remove(pdf_path)
        except OSError:
            pass

        await callback.message.answer_document(
            document=BufferedInputFile(pdf_bytes, filename=filename),
            caption=(
                f"📄 <b>{last_mock.get('exam_label') or last_mock.get('exam_key', 'Mock')} — oxirgi natija</b>\n\n"
                f"🏆 Ball: <b>{last_mock.get('umumiy_ball', '—')}</b>"
                + (f"\n🎖 Daraja: <b>{last_mock['level_label']}</b>" if last_mock.get("level_label") else "")
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


# ─────────────────────────────────────────────────
#  Admin panel: istalgan o'quvchi arxivi (kod bo'yicha)
# ─────────────────────────────────────────────────

@export_router.callback_query(F.data.startswith("talaba_arxiv:"))
async def cb_admin_talaba_arxiv(callback: CallbackQuery, state: FSMContext):
    """Admin panelidan (Talabalarni tahrirlash bo'limi) tanlangan
    o'quvchining ZIP arxivini yuklab beradi."""
    if not await _admin_tekshir(state, callback.from_user.id):
        await callback.answer("⛔ Ruxsat yo'q.", show_alert=True)
        return

    kod = callback.data.split(":", 1)[1]
    await callback.answer()
    status_msg = await callback.message.answer(
        f"⏳ <b>{kod}</b> uchun arxiv tayyorlanmoqda...", parse_mode="HTML"
    )

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, fetch_student_data_by_kod, kod)

        if not data:
            await status_msg.edit_text(f"❌ <b>{kod}</b> kodli o'quvchi topilmadi.", parse_mode="HTML")
            return

        if not data["mock_results"] and not data["dtm_results"] and not data["mini_results"]:
            await status_msg.edit_text(
                f"📭 <b>{kod}</b> uchun hali hech qanday natija yo'q.", parse_mode="HTML"
            )
            return

        zip_buf = await loop.run_in_executor(None, build_zip_archive, data)

        safe_name = (data["student"].get("ismlar") or kod).replace(" ", "_")
        filename = f"{safe_name}_arxiv.zip"

        await callback.message.answer_document(
            document=BufferedInputFile(zip_buf.read(), filename=filename),
            caption=(
                f"✅ <b>{data['student'].get('ismlar', kod)}</b> ({kod}) — arxiv tayyor!\n\n"
                f"📊 Mock natijalari: <b>{len(data['mock_results'])} ta</b>\n"
                f"🎯 Asosiy DTM: <b>{len(data['dtm_results'])} ta</b>\n"
                f"📝 Mini-testlar: <b>{len(data['mini_results'])} ta</b>"
            ),
            parse_mode="HTML",
        )
        await status_msg.delete()

    except Exception as e:
        logger.exception("Admin arxiv xatosi: %s", e)
        await status_msg.edit_text("⚠️ Arxiv yaratishda xato yuz berdi.")
