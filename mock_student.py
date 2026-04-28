"""
Mock imtihon natijalarini ko'rish — O'QUVCHI paneli.

O'quvchi quyidagilarni ko'rishi mumkin:
  - Barcha mock natijalari (IELTS, CEFR, SAT, va boshqalar)
  - Har bir imtihon turi bo'yicha oxirgi natija
  - Natijalar tarixi (dinamika)
"""

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,"""
Mock imtihon natijalari — O'QUVCHI moduli.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import talaba_topish, check_access
from mock_database import (
    exam_type_ol,
    mock_natijalari_ol,
    mock_natija_turlari,
    format_mock_natija_matn,
)

router = Router()


class MockKor(StatesGroup):
    kod_kutish = State()


# ─── YORDAMCHI ───────────────────────────────────────────────

def _turlar_kb(kod: str, turlari: list):
    buttons = [[InlineKeyboardButton(
        text=f"{t['exam_label']} ({t['soni']})",
        callback_data=f"st_mock_type:{kod}:{t['exam_key']}"
    )] for t in turlari]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _detail_kb(kod: str, exam_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Natijalar tarixi", callback_data=f"st_mock_hist:{kod}:{exam_key}")],
        [InlineKeyboardButton(text="⬅️ Orqaga",           callback_data=f"st_mock_back:{kod}")],
    ])


def _back_kb(kod: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"st_mock_back:{kod}")]
    ])


def _overview_text(ismlar: str, turlari: list, kod: str) -> str:
    lines = [f"🧪 <b>{ismlar}</b> — Mock natijalari\n"]
    for t in turlari:
        n = mock_natijalari_ol(kod, exam_key=t["exam_key"], limit=1)
        if not n:
            continue
        natija = n[0]
        et = exam_type_ol(t["exam_key"]) or {}
        umumiy = natija.get("umumiy_ball")
        total_max = et.get("total_max")
        sana = str(natija.get("test_sanasi", ""))[:10]

        if umumiy is not None:
            ball = f"<b>{umumiy}</b>/{total_max}" if total_max else f"<b>{umumiy}</b>"
        else:
            secs = natija.get("sections", {})
            ball = " | ".join(f"{v}" for v in secs.values())

        line = f"• {t['exam_label']}: {ball} ({sana})"
        if natija.get("level_label"):
            line += f" — <b>{natija['level_label']}</b>"
        lines.append(line)

    lines.append("\n👇 <b>Batafsil ko'rish uchun tanlang:</b>")
    return "\n".join(lines)


# ─── ASOSIY HANDLER ──────────────────────────────────────────

@router.message(F.text == "🧪 Mock natijalarim")
async def mock_natijalarim(message: Message, state: FSMContext):
    user_id = message.from_user.id
    talaba = check_access(user_id)

    if not talaba:
        await state.set_state(MockKor.kod_kutish)
        await message.answer(
            "🔍 Mock natijalaringizni ko'rish uchun <b>kodingizni</b> kiriting:",
            parse_mode="HTML",
        )
        return

    await _show_overview(message, talaba["kod"], edit=False)


@router.message(MockKor.kod_kutish)
async def mock_kor_kod(message: Message, state: FSMContext):
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer("❌ Kod topilmadi. Qayta kiriting:")
        return
    await state.clear()
    await _show_overview(message, kod, edit=False)


async def _show_overview(message: Message, kod: str, edit: bool = False):
    talaba = talaba_topish(kod)
    turlari = mock_natija_turlari(kod)

    if not turlari:
        text = (
            f"👤 <b>{talaba['ismlar']}</b>, hali mock natijalar kiritilmagan.\n\n"
            "📌 Natijalar admin tomonidan kiritilganda shu yerda ko'rinadi."
        )
        if edit:
            await message.edit_text(text, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")
        return

    text = _overview_text(talaba["ismlar"], turlari, kod)
    kb = _turlar_kb(kod, turlari)

    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


# ─── IMTIHON TURI TANLANDI ───────────────────────────────────

@router.callback_query(F.data.startswith("st_mock_type:"))
async def st_mock_type(cb: CallbackQuery, state: FSMContext):
    _, kod, exam_key = cb.data.split(":")
    natijalari = mock_natijalari_ol(kod, exam_key=exam_key, limit=1)
    if not natijalari:
        await cb.answer("Natijalar topilmadi", show_alert=True)
        return

    talaba = talaba_topish(kod)
    et = exam_type_ol(exam_key) or {}
    natija = natijalari[0]

    matn = (
        f"👤 <b>{talaba['ismlar']}</b>  <code>{kod}</code>\n\n"
        + format_mock_natija_matn(natija, et)
    )
    await cb.message.edit_text(matn, parse_mode="HTML", reply_markup=_detail_kb(kod, exam_key))
    await cb.answer()


# ─── NATIJALAR TARIXI ─────────────────────────────────────────

@router.callback_query(F.data.startswith("st_mock_hist:"))
async def st_mock_hist(cb: CallbackQuery, state: FSMContext):
    _, kod, exam_key = cb.data.split(":")
    natijalari = mock_natijalari_ol(kod, exam_key=exam_key, limit=10)
    if not natijalari:
        await cb.answer("Topilmadi", show_alert=True)
        return

    et = exam_type_ol(exam_key) or {}
    talaba = talaba_topish(kod)
    total_max = et.get("total_max")

    lines = [f"📅 <b>{talaba['ismlar']} — {et.get('label', exam_key)} tarixi</b>\n"]
    for i, n in enumerate(natijalari, 1):
        sana = str(n.get("test_sanasi", ""))[:10]
        umumiy = n.get("umumiy_ball")
        if umumiy is not None:
            ball = f"{umumiy}/{total_max}" if total_max else str(umumiy)
        else:
            secs = n.get("sections", {})
            ball = " | ".join(f"{k}: {v}" for k, v in secs.items())

        lines.append(f"<b>{i}. {sana}</b> — {ball}")
        if n.get("level_label"):
            lines.append(f"   🎯 {n['level_label']}")
        if n.get("notes"):
            lines.append(f"   📝 {n['notes']}")

    # Dinamika
    balls = [n["umumiy_ball"] for n in natijalari if n.get("umumiy_ball") is not None]
    if len(balls) >= 2:
        farq = balls[0] - balls[1]
        emoji = "📈" if farq > 0 else ("📉" if farq < 0 else "➡️")
        lines.append(f"\n{emoji} Oxirgi 2 natija farqi: <b>{farq:+.1f}</b>")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n<i>...qolganlar qisqartirildi</i>"

    await cb.message.edit_text(text, parse_mode="HTML", reply_markup=_back_kb(kod))
    await cb.answer()


# ─── ORQAGA ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("st_mock_back:"))
async def st_mock_back(cb: CallbackQuery, state: FSMContext):
    kod = cb.data.split(":")[1]
    await _show_overview(cb.message, kod, edit=True)
    await cb.answer()
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import talaba_topish, check_access
from mock_database import (
    EXAM_TYPES,
    mock_natijalari_ol,
    mock_natija_turlari,
    format_mock_natija_matn,
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
            callback_data=f"student_mock_type:{kod}:{t['exam_type']}"
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
        natijalari = mock_natijalari_ol(kod, exam_type=t["exam_type"], limit=1)
        if natijalari:
            natija = natijalari[0]
            # Faqat oxirgi natijaning qisqa ko'rinishi
            umumiy = natija.get("umumiy_ball")
            sana = str(natija.get("test_sanasi", ""))[:10]
            cfg = EXAM_TYPES.get(t["exam_type"], EXAM_TYPES["CUSTOM"])
            total_max = cfg.get("total_max")

            if umumiy is not None:
                ball_text = f"<b>{umumiy}</b>/{total_max}" if total_max else f"<b>{umumiy}</b>"
            else:
                # Band score yoki to'g'ridan-to'g'ri ballar
                sections = natija.get("sections", {})
                ball_parts = []
                for k, v in sections.items():
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
    exam_type = parts[2]

    natijalari = mock_natijalari_ol(kod, exam_type=exam_type, limit=1)
    if not natijalari:
        await callback.answer("Natijalar topilmadi", show_alert=True)
        return

    natija = natijalari[0]
    talaba = talaba_topish(kod)
    cfg = EXAM_TYPES.get(exam_type, EXAM_TYPES["CUSTOM"])

    matn = (
        f"👤 <b>{talaba['ismlar']}</b>\n"
        f"🆔 Kod: <code>{kod}</code>\n\n"
        + format_mock_natija_matn(natija)
    )

    await callback.message.edit_text(
        matn,
        parse_mode="HTML",
        reply_markup=_mock_history_keyboard(kod, exam_type),
    )
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# NATIJALAR TARIXI
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("student_mock_history:"))
async def student_mock_history(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    kod = parts[1]
    exam_type = parts[2]

    natijalari = mock_natijalari_ol(kod, exam_type=exam_type, limit=10)
    if not natijalari:
        await callback.answer("Natijalar topilmadi", show_alert=True)
        return

    cfg = EXAM_TYPES.get(exam_type, EXAM_TYPES["CUSTOM"])
    talaba = talaba_topish(kod)

    lines = [
        f"📅 <b>{talaba['ismlar']}</b> — {cfg['label']} tarixi\n"
    ]

    for i, n in enumerate(natijalari, 1):
        sana = str(n.get("test_sanasi", ""))[:10]
        umumiy = n.get("umumiy_ball")
        total_max = cfg.get("total_max")

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
        natijalari = mock_natijalari_ol(kod, exam_type=t["exam_type"], limit=1)
        if natijalari:
            n = natijalari[0]
            umumiy = n.get("umumiy_ball")
            cfg = EXAM_TYPES.get(t["exam_type"], EXAM_TYPES["CUSTOM"])
            total_max = cfg.get("total_max")
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
