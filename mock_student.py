from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from database import check_access, talaba_topish
from mock_database import (
    exam_type_ol,
    format_mock_natija_matn,
    mock_natija_turlari,
    mock_natijalari_ol,
)

router = Router()


# ─────────────────────────────────────────────────────────────
# FSM HOLATLARI
# ─────────────────────────────────────────────────────────────

class MockNatijaKor(StatesGroup):
    kod_kutish = State()


# ─────────────────────────────────────────────────────────────
# YORDAMCHI FUNKSIYALAR
# ─────────────────────────────────────────────────────────────

def _mock_turlar_keyboard(kod: str, turlari: list):
    """O'quvchi uchun imtihon turlari tugmalari."""
    buttons = []
    for t in turlari:
        buttons.append([InlineKeyboardButton(
            text=f"{t['exam_label']} ({t['soni']} ta)",
            callback_data=f"student_mock_type:{kod}:{t['exam_key']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _mock_history_keyboard(kod: str, exam_type: str):
    """Natijalar tarixi ko'rsatish tugmasi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📅 Barcha natijalar (tarixi)",
            callback_data=f"student_mock_history:{kod}:{exam_type}"
        )],
        [InlineKeyboardButton(
            text="⬅️ Orqaga",
            callback_data=f"student_mock_back:{kod}"
        )],
    ])


# ─────────────────────────────────────────────────────────────
# ASOSIY HANDLER
# ─────────────────────────────────────────────────────────────

@router.message(F.text == "🧪 Mock natijalarim")
async def mock_natijalarim_start(message: Message, state: FSMContext):
    """O'quvchi 'Mock natijalarim' tugmasini bosadi."""
    user_id = message.from_user.id

    # Ulangan talabani topish
    talaba = check_access(user_id)
    if not talaba:
        await state.set_state(MockNatijaKor.kod_kutish)
        await message.answer(
            "🔍 Mock natijalaringizni ko'rish uchun shaxsiy <b>kodingizni</b> kiriting:",
            parse_mode="HTML",
        )
        return

    await _show_mock_types(message, talaba["kod"])


@router.message(MockNatijaKor.kod_kutish)
async def mock_kor_kod(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer("❌ Bunday kod topilmadi. Qayta kiriting:")
        return

    await state.clear()
    await _show_mock_types(message, kod)


async def _show_mock_types(message: Message, kod: str):
    """O'quvchining mock natijasi turlarini ko'rsatish."""
    talaba = talaba_topish(kod)
    turlari = mock_natija_turlari(kod)

    if not turlari:
        await message.answer(
            f"👤 <b>{talaba['ismlar']}</b>, sizda hali mock natijalar mavjud emas.\n\n"
            "📌 Natijalar admin tomonidan kiritilganda bu yerda ko'rinadi.",
            parse_mode="HTML",
        )
        return

    # Har bir turning oxirgi natijasini ko'rsatish
    lines = [
        f"🧪 <b>{talaba['ismlar']}</b> — Mock natijalari\n",
        f"📊 Jami {len(turlari)} xil imtihon natijalari mavjud:\n",
    ]

    for t in turlari:
        exam_key = t.get("exam_key")
        natijalari = mock_natijalari_ol(kod, exam_key=exam_key, limit=1)
        if natijalari:
            natija = natijalari[0]
            # Faqat oxirgi natijaning qisqa ko'rinishi
            umumiy = natija.get("umumiy_ball")
            sana = str(natija.get("test_sanasi", ""))[:10]
            et = exam_type_ol(exam_key) or {}
            total_max = et.get("total_max")

            if umumiy is not None:
                ball_text = f"<b>{umumiy}</b>/{total_max}" if total_max else f"<b>{umumiy}</b>"
            else:
                # Band score yoki to'g'ridan-to'g'ri ballar
                sections = natija.get("sections", {})
                ball_parts = []
                for k, v in sections.items():
                    if isinstance(v, dict) and "value" in v:
                        ball_parts.append(f"{v.get('value')}")
                    else:
                        ball_parts.append(f"{v}")
                ball_text = " | ".join(ball_parts)

            lines.append(f"• {t['exam_label']}: {ball_text} ({sana})")

            if natija.get("level_label"):
                lines.append(f"  🎯 Daraja: <b>{natija['level_label']}</b>")

    await message.answer(
        "\n".join(lines) + "\n\n👇 <b>Batafsil ko'rish uchun tanlang:</b>",
        parse_mode="HTML",
        reply_markup=_mock_turlar_keyboard(kod, turlari),
    )


# ─────────────────────────────────────────────────────────────
# IMTIHON TURI TANLANDI
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("student_mock_type:"))
async def student_mock_type(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    kod = parts[1]
    exam_key = parts[2]

    natijalari = mock_natijalari_ol(kod, exam_key=exam_key, limit=1)
    if not natijalari:
        await callback.answer("Natijalar topilmadi", show_alert=True)
        return

    natija = natijalari[0]
    talaba = talaba_topish(kod)
    et = exam_type_ol(exam_key) or {}

    matn = (
        f"👤 <b>{talaba['ismlar']}</b>\n"
        f"🆔 Kod: <code>{kod}</code>\n\n"
        + format_mock_natija_matn(natija)
    )

    await callback.message.edit_text(
        matn,
        parse_mode="HTML",
        reply_markup=_mock_history_keyboard(kod, exam_key),
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# NATIJALAR TARIXI
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("student_mock_history:"))
async def student_mock_history(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    kod = parts[1]
    exam_key = parts[2]

    natijalari = mock_natijalari_ol(kod, exam_key=exam_key, limit=10)
    if not natijalari:
        await callback.answer("Natijalar topilmadi", show_alert=True)
        return

    et = exam_type_ol(exam_key) or {"label": "Mock"}
    talaba = talaba_topish(kod)

    lines = [
        f"📅 <b>{talaba['ismlar']}</b> — {et.get('label', 'Mock')} tarixi\n"
    ]

    for i, n in enumerate(natijalari, 1):
        sana = str(n.get("test_sanasi", ""))[:10]
        umumiy = n.get("umumiy_ball")
        total_max = et.get("total_max")

        if umumiy is not None:
            ball = f"{umumiy}/{total_max}" if total_max else str(umumiy)
        else:
            sections = n.get("sections", {})
            ball = " | ".join(f"{k}: {v}" for k, v in sections.items())

        lines.append(f"<b>{i}. {sana}</b> — {ball}")

        if n.get("level_label"):
            lines.append(f"   🎯 {n['level_label']}")
        if n.get("notes"):
            lines.append(f"   📝 {n['notes']}")

    # Dinamika (agar umumiy ball bo'lsa)
    balls = [n["umumiy_ball"] for n in natijalari if n.get("umumiy_ball") is not None]
    if len(balls) >= 2:
        farq = balls[0] - balls[1]
        emoji = "📈" if farq > 0 else ("📉" if farq < 0 else "➡️")
        lines.append(f"\n{emoji} Oxirgi ikki natija farqi: <b>{farq:+.1f}</b>")

    text = "\n".join(lines)
    back_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⬅️ Orqaga",
            callback_data=f"student_mock_back:{kod}"
        )]
    ])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=back_markup)
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# ORQAGA TUGMASI
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("student_mock_back:"))
async def student_mock_back(callback: CallbackQuery, state: FSMContext):
    kod = callback.data.split(":")[1]
    turlari = mock_natija_turlari(kod)
    talaba = talaba_topish(kod)

    if not turlari or not talaba:
        await callback.message.edit_text("❌ Ma'lumotlar topilmadi.")
        await callback.answer()
        return

    lines = [f"🧪 <b>{talaba['ismlar']}</b> — Mock natijalari\n"]
    for t in turlari:
        exam_key = t.get("exam_key")
        natijalari = mock_natijalari_ol(kod, exam_key=exam_key, limit=1)
        if natijalari:
            n = natijalari[0]
            umumiy = n.get("umumiy_ball")
            et = exam_type_ol(exam_key) or {}
            total_max = et.get("total_max")
            sana = str(n.get("test_sanasi", ""))[:10]
            if umumiy is not None:
                ball_text = f"<b>{umumiy}</b>/{total_max}" if total_max else f"<b>{umumiy}</b>"
            else:
                sections = n.get("sections", {})
                ball_text = " | ".join(f"{v}" for v in sections.values())
            lines.append(f"• {t['exam_label']}: {ball_text} ({sana})")

    await callback.message.edit_text(
        "\n".join(lines) + "\n\n👇 <b>Batafsil ko'rish uchun tanlang:</b>",
        parse_mode="HTML",
        reply_markup=_mock_turlar_keyboard(kod, turlari),
    )
    await callback.answer()
