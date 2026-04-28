"""
Mock imtihon natijalarini boshqarish — ADMIN paneli.

Admin quyidagi amallarni bajarishi mumkin:
  1. Yangi mock natijasini kiritish (IELTS, CEFR, SAT, Milliy sertifikat, va boshqalar)
  2. Mavjud mock natijasini ko'rish / o'chirish
  3. Sinf bo'yicha statistika
"""

import asyncio
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import talaba_topish
from mock_database import (
    EXAM_TYPES,
    mock_natija_qosh,
    mock_natijalari_ol,
    mock_natija_ochir,
    mock_natija_turlari,
    format_mock_natija_matn,
)

router = Router()


# ─────────────────────────────────────────────────────────────
# FSM HOLATLARI
# ─────────────────────────────────────────────────────────────

class MockNatijaQosh(StatesGroup):
    exam_type_kutish = State()
    talaba_kod_kutish = State()
    subject_name_kutish = State()  # Milliy sertifikat uchun
    section_kutish = State()       # Har bir bo'lim uchun navbatma-navbat
    level_kutish = State()         # CEFR daraja tanlash
    notes_kutish = State()
    tasdiq_kutish = State()


class MockNatijaKor(StatesGroup):
    kod_kutish = State()
    exam_type_kutish = State()


class MockNatijaOchir(StatesGroup):
    kod_kutish = State()
    natija_id_kutish = State()


# ─────────────────────────────────────────────────────────────
# YORDAMCHI FUNKSIYALAR
# ─────────────────────────────────────────────────────────────

def _exam_type_keyboard():
    """Imtihon turi tanlash klaviaturasi."""
    buttons = []
    for key, cfg in EXAM_TYPES.items():
        if key == "CUSTOM":
            continue
        buttons.append([InlineKeyboardButton(
            text=cfg["label"],
            callback_data=f"mock_exam_type:{key}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="mock_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _level_keyboard(exam_type: str):
    """Daraja tanlash (CEFR)."""
    cfg = EXAM_TYPES.get(exam_type, {})
    levels = cfg.get("levels", [])
    buttons = [[InlineKeyboardButton(
        text=lv, callback_data=f"mock_level:{lv}"
    )] for lv in levels]
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="mock_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _tasdiq_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Saqlash", callback_data="mock_save_yes"),
            InlineKeyboardButton(text="❌ Bekor", callback_data="mock_cancel"),
        ]
    ])


async def _admin_tekshir(state: FSMContext, user_id: int) -> bool:
    """Admin huquqini tekshirish (mavjud admin moduldan)."""
    from admin import is_admin_id
    return is_admin_id(user_id)


def _build_confirm_text(data: dict) -> str:
    """Tasdiqlash matni."""
    exam_type = data.get("exam_type", "CUSTOM")
    cfg = EXAM_TYPES.get(exam_type, EXAM_TYPES["CUSTOM"])
    sections = data.get("sections", {})

    lines = [
        "📋 <b>Yangi mock natijasi</b>",
        f"👤 O'quvchi: <b>{data.get('ismlar', '')} ({data.get('talaba_kod', '')})</b>",
        f"📝 Imtihon turi: <b>{cfg['label']}</b>",
        "",
    ]

    if data.get("subject_name"):
        lines.append(f"📚 Fan: <b>{data['subject_name']}</b>")

    section_labels = cfg.get("section_labels", {})
    max_scores = cfg.get("max_scores", {})

    for sec_key, sec_val in sections.items():
        label = section_labels.get(sec_key, sec_key)
        max_val = max_scores.get(sec_key)
        if max_val:
            lines.append(f"{label}: <b>{sec_val}</b> / {max_val}")
        else:
            lines.append(f"{label}: <b>{sec_val}</b>")

    if data.get("level"):
        lines.append(f"🎯 Daraja: <b>{data['level']}</b>")
    if data.get("notes"):
        lines.append(f"📝 Izoh: {data['notes']}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# MOCK NATIJASI QO'SHISH — ASOSIY FLOW
# ─────────────────────────────────────────────────────────────

@router.message(F.text == "📝 Mock natija qo'shish")
async def mock_natija_qosh_start(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return

    await state.set_state(MockNatijaQosh.exam_type_kutish)
    await message.answer(
        "📋 <b>Imtihon turini tanlang:</b>",
        parse_mode="HTML",
        reply_markup=_exam_type_keyboard(),
    )


@router.callback_query(F.data.startswith("mock_exam_type:"), MockNatijaQosh.exam_type_kutish)
async def mock_exam_type_tanlandi(callback: CallbackQuery, state: FSMContext):
    exam_type = callback.data.split(":")[1]
    cfg = EXAM_TYPES.get(exam_type)
    if not cfg:
        await callback.answer("Noma'lum tur!", show_alert=True)
        return

    await state.update_data(exam_type=exam_type, sections={}, current_section_idx=0)
    await state.set_state(MockNatijaQosh.talaba_kod_kutish)
    await callback.message.edit_text(
        f"✅ <b>{cfg['label']}</b> tanlandi.\n\n🔍 O'quvchi <b>kodini</b> kiriting:",
        parse_mode="HTML",
    )


@router.message(MockNatijaQosh.talaba_kod_kutish)
async def mock_talaba_kod(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer("❌ Bunday kodli o'quvchi topilmadi. Qayta kiriting:")
        return

    data = await state.get_data()
    exam_type = data["exam_type"]
    cfg = EXAM_TYPES[exam_type]

    await state.update_data(talaba_kod=kod, ismlar=talaba["ismlar"])

    # Milliy sertifikat uchun fan nomi so'rash
    if cfg.get("has_subject"):
        await state.set_state(MockNatijaQosh.subject_name_kutish)
        await message.answer(
            f"👤 O'quvchi: <b>{talaba['ismlar']}</b>\n\n📚 <b>Fan nomini kiriting</b> (masalan: Fizika, Kimyo):",
            parse_mode="HTML",
        )
        return

    # Bo'limlarga o'tish
    await _ask_next_section(message, state)


@router.message(MockNatijaQosh.subject_name_kutish)
async def mock_subject_name(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return
    subject = message.text.strip()
    await state.update_data(subject_name=subject)
    await _ask_next_section(message, state)


async def _ask_next_section(message: Message, state: FSMContext):
    """Keyingi bo'lim uchun ball so'rash."""
    data = await state.get_data()
    exam_type = data["exam_type"]
    cfg = EXAM_TYPES[exam_type]
    sections_list = cfg.get("sections", [])
    idx = data.get("current_section_idx", 0)

    # Faqat bitta "ball" bo'limi bo'lsa (Ingliz tili, Ona tili, Matematika)
    if len(sections_list) == 1 and sections_list[0] == "ball":
        max_val = cfg["max_scores"].get("ball", 100)
        await state.set_state(MockNatijaQosh.section_kutish)
        await message.answer(
            f"📊 <b>Balini kiriting</b> (0–{max_val}):",
            parse_mode="HTML",
        )
        return

    if idx < len(sections_list):
        sec_key = sections_list[idx]
        sec_label = cfg["section_labels"].get(sec_key, sec_key)
        max_val = cfg["max_scores"].get(sec_key, "")
        max_hint = f" (0–{max_val})" if max_val else ""

        await state.update_data(current_section_key=sec_key)
        await state.set_state(MockNatijaQosh.section_kutish)
        await message.answer(
            f"{sec_label} bo'yicha natijani kiriting{max_hint}:",
            parse_mode="HTML",
        )
    else:
        # Barcha bo'limlar kiritildi
        await _after_all_sections(message, state)


@router.message(MockNatijaQosh.section_kutish)
async def mock_section_kiritish(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return

    text = message.text.strip().replace(",", ".")
    try:
        val = float(text)
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return

    data = await state.get_data()
    exam_type = data["exam_type"]
    cfg = EXAM_TYPES[exam_type]
    sections_list = cfg.get("sections", [])

    # Bitta bo'lim holati
    if len(sections_list) == 1 and sections_list[0] == "ball":
        max_val = cfg["max_scores"].get("ball", 100)
        if not (0 <= val <= max_val):
            await message.answer(f"❌ Ball 0 va {max_val} orasida bo'lishi kerak:")
            return
        sections = {**data.get("sections", {}), "ball": val}
        await state.update_data(sections=sections, current_section_idx=1)
        await _after_all_sections(message, state)
        return

    # Ko'p bo'limli holat
    sec_key = data.get("current_section_key")
    max_val = cfg["max_scores"].get(sec_key)
    if max_val is not None and not (0 <= val <= max_val):
        await message.answer(f"❌ Qiymat 0 va {max_val} orasida bo'lishi kerak:")
        return

    sections = {**data.get("sections", {}), sec_key: val}
    idx = data.get("current_section_idx", 0) + 1
    await state.update_data(sections=sections, current_section_idx=idx)
    await _ask_next_section(message, state)


async def _after_all_sections(message: Message, state: FSMContext):
    """Barcha bo'limlar kiritilgandan so'ng."""
    data = await state.get_data()
    exam_type = data["exam_type"]
    cfg = EXAM_TYPES[exam_type]

    # CEFR uchun daraja tanlash
    if cfg.get("has_level"):
        await state.set_state(MockNatijaQosh.level_kutish)
        await message.answer(
            "🎯 <b>Darajani tanlang:</b>",
            parse_mode="HTML",
            reply_markup=_level_keyboard(exam_type),
        )
        return

    # Izoh (ixtiyoriy)
    await _ask_notes(message, state)


@router.callback_query(F.data.startswith("mock_level:"), MockNatijaQosh.level_kutish)
async def mock_level_tanlandi(callback: CallbackQuery, state: FSMContext):
    level = callback.data.split(":")[1]
    await state.update_data(level=level)
    await callback.message.delete()
    await _ask_notes(callback.message, state)


async def _ask_notes(message: Message, state: FSMContext):
    await state.set_state(MockNatijaQosh.notes_kutish)
    await message.answer(
        "📝 <b>Izoh qoldiring</b> (ixtiyoriy, o'tkazib yuborish uchun <code>-</code> yozing):",
        parse_mode="HTML",
    )


@router.message(MockNatijaQosh.notes_kutish)
async def mock_notes_kiritish(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return
    notes = message.text.strip()
    if notes == "-":
        notes = None
    await state.update_data(notes=notes)

    # Tasdiqlash
    data = await state.get_data()
    confirm_text = _build_confirm_text(data)
    await state.set_state(MockNatijaQosh.tasdiq_kutish)
    await message.answer(
        f"{confirm_text}\n\n✅ <b>Saqlashni tasdiqlaysizmi?</b>",
        parse_mode="HTML",
        reply_markup=_tasdiq_keyboard(),
    )


@router.callback_query(F.data == "mock_save_yes", MockNatijaQosh.tasdiq_kutish)
async def mock_save_tasdiq(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    new_id = mock_natija_qosh(
        talaba_kod=data["talaba_kod"],
        exam_type=data["exam_type"],
        sections=data.get("sections", {}),
        level_label=data.get("level"),
        subject_name=data.get("subject_name"),
        notes=data.get("notes"),
        admin_id=callback.from_user.id,
    )

    # O'quvchiga xabar yuborish (agar bot ulangan bo'lsa)
    asyncio.create_task(
        _xabar_yuborish_talabaga(callback.bot, data["talaba_kod"], new_id)
    )

    await callback.message.edit_text(
        f"✅ <b>Mock natijasi muvaffaqiyatli saqlandi!</b> (ID: {new_id})\n\n"
        f"👤 {data.get('ismlar')} — {EXAM_TYPES[data['exam_type']]['label']}",
        parse_mode="HTML",
    )
    await state.clear()


async def _xabar_yuborish_talabaga(bot, talaba_kod: str, natija_id: int):
    """O'quvchiga yangi mock natijasi haqida xabar yuborish."""
    try:
        from database import talaba_topish
        talaba = talaba_topish(talaba_kod)
        if not talaba or not talaba.get("user_id"):
            return

        natijalari = mock_natijalari_ol(talaba_kod, limit=1)
        if not natijalari:
            return

        natija = natijalari[0]
        matn = (
            f"🔔 <b>Yangi natijangiz qo'shildi!</b>\n\n"
            + format_mock_natija_matn(natija)
        )
        await bot.send_message(
            talaba["user_id"],
            matn,
            parse_mode="HTML",
        )
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# MOCK NATIJALARINI KO'RISH (ADMIN)
# ─────────────────────────────────────────────────────────────

@router.message(F.text == "📊 Mock natijalarini ko'rish")
async def mock_natija_kor_start(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return
    await state.set_state(MockNatijaKor.kod_kutish)
    await message.answer(
        "🔍 O'quvchi <b>kodini</b> kiriting:",
        parse_mode="HTML",
    )


@router.message(MockNatijaKor.kod_kutish)
async def mock_kor_kod(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer("❌ Bunday kodli o'quvchi topilmadi.")
        await state.clear()
        return

    turlari = mock_natija_turlari(kod)
    if not turlari:
        await message.answer(
            f"👤 <b>{talaba['ismlar']}</b> uchun mock natijalari mavjud emas.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    # Har bir tur uchun oxirgi natijani ko'rsatish
    await state.update_data(talaba_kod=kod)

    lines = [f"👤 <b>{talaba['ismlar']} ({kod})</b> — Mock natijalari:\n"]
    for t in turlari:
        natijalari = mock_natijalari_ol(kod, exam_type=t["exam_type"], limit=1)
        if natijalari:
            natija = natijalari[0]
            lines.append(format_mock_natija_matn(natija))
            lines.append(f"📊 Jami: {t['soni']} ta natija")
            lines.append("─────────────────")

    # Inline tugmalar: har bir tur uchun "Barchasini ko'rish"
    buttons = []
    for t in turlari:
        buttons.append([InlineKeyboardButton(
            text=f"📋 {t['exam_label']} — barcha ({t['soni']})",
            callback_data=f"mock_view_all:{kod}:{t['exam_type']}"
        )])
    buttons.append([InlineKeyboardButton(
        text="🗑️ Natija o'chirish", callback_data=f"mock_delete_start:{kod}"
    )])
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.clear()


@router.callback_query(F.data.startswith("mock_view_all:"))
async def mock_view_all(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    kod = parts[1]
    exam_type = parts[2]

    natijalari = mock_natijalari_ol(kod, exam_type=exam_type, limit=10)
    if not natijalari:
        await callback.answer("Natijalar topilmadi", show_alert=True)
        return

    cfg = EXAM_TYPES.get(exam_type, EXAM_TYPES["CUSTOM"])
    lines = [f"📋 <b>{cfg['label']} — barcha natijalar:</b>\n"]
    for i, n in enumerate(natijalari, 1):
        lines.append(f"<b>{i}.</b> " + format_mock_natija_matn(n))
        lines.append(f"🆔 ID: {n['id']}")
        lines.append("─────────────")

    text = "\n".join(lines)
    # Uzun bo'lsa bo'laklarga ajratish
    if len(text) > 4000:
        text = text[:3900] + "\n...(qolgan natijalar qisqartirildi)"

    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


# ─────────────────────────────────────────────────────────────
# MOCK NATIJASINI O'CHIRISH
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("mock_delete_start:"))
async def mock_delete_start(callback: CallbackQuery, state: FSMContext):
    kod = callback.data.split(":")[1]
    await state.set_state(MockNatijaOchir.natija_id_kutish)
    await state.update_data(talaba_kod=kod)
    await callback.message.answer(
        "🗑️ O'chirish uchun natija <b>ID raqamini</b> kiriting\n"
        "(Natija ID sini yuqoridagi ro'yxatdan ko'ring):",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(MockNatijaOchir.natija_id_kutish)
async def mock_delete_natija(message: Message, state: FSMContext):
    if not await _admin_tekshir(state, message.from_user.id):
        return
    try:
        natija_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting.")
        return

    deleted = mock_natija_ochir(natija_id)
    if deleted:
        await message.answer(f"✅ Natija (ID: {natija_id}) muvaffaqiyatli o'chirildi.")
    else:
        await message.answer(f"❌ ID {natija_id} bilan natija topilmadi.")
    await state.clear()


# ─────────────────────────────────────────────────────────────
# BEKOR QILISH
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "mock_cancel")
async def mock_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Amal bekor qilindi.")
