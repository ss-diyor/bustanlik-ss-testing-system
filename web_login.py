"""mock.sultanov.space uchun Telegram orqali web-kirish tasdiqlashi."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

import mock_exam_engine as engine


router = Router()


@router.callback_query(F.data.startswith("web_login:"))
async def web_login_javobi(callback: CallbackQuery):
    """O'quvchi faqat o'z Telegram akkauntidan kelgan so'rovni tasdiqlaydi."""
    try:
        _, action, token = callback.data.split(":", 2)
        approved = action == "approve"
        if action not in {"approve", "reject"}:
            raise ValueError("Noto'g'ri amal")
    except (ValueError, AttributeError):
        await callback.answer("So'rov noto'g'ri", show_alert=True)
        return

    result, error = engine.web_login_sorov_javob(token, callback.from_user.id, approved)
    if error:
        await callback.answer(error, show_alert=True)
        return

    if result:
        await callback.answer("Saytga kirish tasdiqlandi", show_alert=True)
        if callback.message:
            await callback.message.edit_text(
                "✅ <b>Saytga kirish tasdiqlandi.</b>\n\n"
                "Brauzerdagi sahifa avtomatik ravishda ochiladi.",
                parse_mode="HTML",
            )
    else:
        await callback.answer("So'rov rad etildi", show_alert=True)
        if callback.message:
            await callback.message.edit_text(
                "❌ <b>Saytga kirish so'rovi rad etildi.</b>",
                parse_mode="HTML",
            )
