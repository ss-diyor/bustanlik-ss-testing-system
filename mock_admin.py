"""
Mock imtihon — ADMIN moduli.
Menyular:
  📝 Mock natija qo'shish     — natija kiritish
  📊 Mock natijalarini ko'rish — ko'rish / o'chirish
  ⚙️ Mock fanlar boshqaruvi   — exam type qo'shish / o'chirish / holat
"""

import asyncio
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import talaba_topish
from mock_database import (
    exam_types_ol, exam_type_ol,
    exam_type_qosh, exam_type_ochir, exam_type_holat,
    mock_natija_qosh, mock_natijalari_ol,
    mock_natija_ochir, mock_natija_turlari,
    format_mock_natija_matn,
)

router = Router()


# ════════════════════════════════════════════════════════════
# FSM HOLATLARI
# ════════════════════════════════════════════════════════════

class MockNatijaQosh(StatesGroup):
    exam_key_kutish     = State()
    talaba_kod_kutish   = State()
    subject_kutish      = State()    # MILLIY_SERT uchun
    schema_kutish       = State()    # admin section/daraja formatini kiritadi
    levels_kutish       = State()    # admin darajalar ro'yxatini ixtiyoriy kiritadi
    section_kutish      = State()    # navbatma-navbat bo'limlar
    level_kutish        = State()    # CEFR daraja
    notes_kutish        = State()
    tasdiq_kutish       = State()


class MockNatijaKor(StatesGroup):
    kod_kutish = State()


class MockNatijaOchir(StatesGroup):
    id_kutish = State()


# ── Exam type qo'shish ──────────────────────────────────────
class ExamTypeQosh(StatesGroup):
    label_kutish    = State()    # Inson uchun nom
    key_kutish      = State()    # unikal kalit (auto taklif qilinadi)
    sections_kutish = State()    # bo'limlar ro'yxati (har qatori alohida)
    total_kutish    = State()    # umumiy max ball (ixtiyoriy)
    tasdiq_kutish   = State()


# ════════════════════════════════════════════════════════════
# YORDAMCHI
# ════════════════════════════════════════════════════════════

async def _admin_ok(message_or_cb, state: FSMContext) -> bool:
    from admin import is_admin_id
    uid = (
        message_or_cb.from_user.id
        if hasattr(message_or_cb, "from_user")
        else message_or_cb.from_user.id
    )
    return is_admin_id(uid)


def _exam_list_kb(action: str = "select"):
    """Barcha aktiv exam type larni tugma sifatida chiqaradi."""
    types = exam_types_ol(faqat_aktiv=False)
    buttons = []
    for et in types:
        icon = "✅" if et["is_active"] else "❌"
        lock = "🔒" if et["is_builtin"] else ""
        label = f"{icon}{lock} {et['label']}"
        buttons.append([InlineKeyboardButton(
            text=label, callback_data=f"mock_et_{action}:{et['exam_key']}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Bekor", callback_data="mock_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _tasdiq_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Saqlash", callback_data="mock_save_yes"),
        InlineKeyboardButton(text="❌ Bekor",   callback_data="mock_cancel"),
    ]])


def _level_kb(levels_list: list):
    buttons = [[InlineKeyboardButton(text=lv, callback_data=f"mock_level:{lv}")]
               for lv in levels_list]
    buttons.append([InlineKeyboardButton(text="❌ Bekor", callback_data="mock_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_confirm_text(data: dict) -> str:
    et = exam_type_ol(data.get("exam_key", "")) or {}
    sections = data.get("sections", {})
    lines = [
        "📋 <b>Yangi mock natijasi — tasdiqlash</b>",
        f"👤 O'quvchi: <b>{data.get('ismlar', '')} ({data.get('talaba_kod', '')})</b>",
        f"📝 Imtihon: <b>{et.get('label', data.get('exam_key'))}</b>",
        "",
    ]
    if data.get("subject_name"):
        lines.append(f"📚 Fan: <b>{data['subject_name']}</b>")

    sec_map = {s["section_key"]: s for s in et.get("sections", [])}
    for k, v in sections.items():
        sec = sec_map.get(k, {})
        lbl = sec.get("label", k)
        mx = sec.get("max_score")
        lines.append(f"{lbl}: <b>{v}</b>" + (f" / {mx}" if mx else ""))

    if data.get("level"):
        lines.append(f"🎯 Daraja: <b>{data['level']}</b>")
    if data.get("notes"):
        lines.append(f"📝 Izoh: {data['notes']}")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════
# MOCK FANLAR BOSHQARUVI
# ════════════════════════════════════════════════════════════

@router.message(F.text == "⚙️ Mock fanlar boshqaruvi")
async def mock_fanlar_menu(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    types = exam_types_ol(faqat_aktiv=False)
    lines = ["⚙️ <b>Mock imtihon turlari:</b>\n"]
    for et in types:
        icon  = "✅" if et["is_active"] else "❌"
        lock  = " 🔒" if et["is_builtin"] else ""
        lines.append(f"{icon} {et['label']}{lock}  <code>{et['exam_key']}</code>")
    lines.append("\n<i>🔒 — standart (o'chirib bo'lmaydi)</i>")

    buttons = [
        [InlineKeyboardButton(text="➕ Yangi tur qo'shish",    callback_data="mock_et_add")],
        [InlineKeyboardButton(text="🗑️ Turni o'chirish",       callback_data="mock_et_del_list")],
        [InlineKeyboardButton(text="🔄 Yoqish / O'chirish",    callback_data="mock_et_toggle_list")],
    ]
    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


# ── Yangi exam type qo'shish ────────────────────────────────

@router.callback_query(F.data == "mock_et_add")
async def et_add_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(ExamTypeQosh.label_kutish)
    await cb.message.edit_text(
        "➕ <b>Yangi imtihon turi qo'shish</b>\n\n"
        "1️⃣ Imtihon nomini kiriting (masalan: <code>Ingliz tili mock</code>):",
        parse_mode="HTML",
    )


@router.message(ExamTypeQosh.label_kutish)
async def et_add_label(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    label = message.text.strip()
    # Avtomatik kalit yaratish
    auto_key = re.sub(r"[^A-Za-z0-9]", "_", label.upper())[:20]
    await state.update_data(label=label, exam_key=auto_key)
    await state.set_state(ExamTypeQosh.key_kutish)
    await message.answer(
        f"2️⃣ Unikal kalit (ID) kiriting.\n"
        f"Taklif: <code>{auto_key}</code>\n"
        f"(Shunday qoldirish uchun <code>.</code> yozing)",
        parse_mode="HTML",
    )


@router.message(ExamTypeQosh.key_kutish)
async def et_add_key(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    data = await state.get_data()
    text = message.text.strip()
    if text == ".":
        key = data["exam_key"]
    else:
        key = re.sub(r"[^A-Za-z0-9_]", "_", text.upper())[:30]

    await state.update_data(exam_key=key)
    await state.set_state(ExamTypeQosh.sections_kutish)
    await message.answer(
        f"✅ Kalit: <code>{key}</code>\n\n"
        "3️⃣ <b>Bo'limlarni kiriting</b> — har qatori: <code>kalit | nom | max_ball</code>\n"
        "max_ball ixtiyoriy.\n\n"
        "Misol:\n"
        "<code>listening | 🎧 Listening | 9\n"
        "reading | 📖 Reading | 9\n"
        "writing | ✍️ Writing | 9</code>\n\n"
        "Faqat bitta ball bo'lsa:\n"
        "<code>ball | 📊 Ball | 100</code>",
        parse_mode="HTML",
    )


@router.message(ExamTypeQosh.sections_kutish)
async def et_add_sections(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    sections = []
    errors = []
    for ln in lines:
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < 2:
            errors.append(f"❌ Format xato: <code>{ln}</code>")
            continue
        sec_key = re.sub(r"[^a-z0-9_]", "_", parts[0].lower())
        sec_label = parts[1]
        max_s = None
        if len(parts) >= 3:
            try:
                max_s = float(parts[2])
            except ValueError:
                errors.append(f"⚠️ Max ball raqam emas: <code>{parts[2]}</code>")
        sections.append({"section_key": sec_key, "label": sec_label, "max_score": max_s})

    if errors:
        await message.answer("\n".join(errors) + "\n\nQayta kiriting:", parse_mode="HTML")
        return
    if not sections:
        await message.answer("❌ Kamida 1 ta bo'lim kerak.")
        return

    await state.update_data(sections=sections)
    await state.set_state(ExamTypeQosh.total_kutish)

    sec_preview = "\n".join(
        f"  • {s['section_key']} → {s['label']}"
        + (f" (max: {s['max_score']})" if s["max_score"] else "")
        for s in sections
    )
    await message.answer(
        f"✅ Bo'limlar:\n{sec_preview}\n\n"
        "4️⃣ <b>Umumiy maximum ball</b> kiriting (masalan <code>100</code>).\n"
        "Yo'q bo'lsa <code>-</code> yozing:",
        parse_mode="HTML",
    )


@router.message(ExamTypeQosh.total_kutish)
async def et_add_total(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    text = message.text.strip()
    total_max = None
    if text != "-":
        try:
            total_max = float(text)
        except ValueError:
            await message.answer("❌ Raqam yoki <code>-</code> kiriting:", parse_mode="HTML")
            return
    await state.update_data(total_max=total_max)

    data = await state.get_data()
    sections = data.get("sections", [])
    sec_preview = "\n".join(
        f"  • {s['label']}" + (f" / {s['max_score']}" if s["max_score"] else "")
        for s in sections
    )
    confirm = (
        f"📋 <b>Tasdiqlash:</b>\n"
        f"🔑 Kalit: <code>{data['exam_key']}</code>\n"
        f"📝 Nom: <b>{data['label']}</b>\n"
        f"📊 Bo'limlar:\n{sec_preview}\n"
        f"🏆 Max: <b>{total_max if total_max else 'yo\'q'}</b>\n\n"
        f"Saqlashni tasdiqlaysizmi?"
    )
    await state.set_state(ExamTypeQosh.tasdiq_kutish)
    await message.answer(confirm, parse_mode="HTML", reply_markup=_tasdiq_kb())


@router.callback_query(F.data == "mock_save_yes", ExamTypeQosh.tasdiq_kutish)
async def et_add_save(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ok, msg = exam_type_qosh(
        exam_key=data["exam_key"],
        label=data["label"],
        sections=data.get("sections", []),
        total_max=data.get("total_max"),
    )
    if ok:
        await cb.message.edit_text(
            f"✅ <b>{data['label']}</b> muvaffaqiyatli qo'shildi!\n"
            f"Kalit: <code>{data['exam_key']}</code>",
            parse_mode="HTML",
        )
    else:
        await cb.message.edit_text(
            f"❌ Xatolik: {msg}\n(Ehtimol bu kalit allaqachon mavjud)",
            parse_mode="HTML",
        )
    await state.clear()


# ── Exam type o'chirish ─────────────────────────────────────

@router.callback_query(F.data == "mock_et_del_list")
async def et_del_list(cb: CallbackQuery, state: FSMContext):
    types = exam_types_ol(faqat_aktiv=False)
    buttons = []
    for et in types:
        if not et["is_builtin"]:
            buttons.append([InlineKeyboardButton(
                text=f"🗑️ {et['label']}",
                callback_data=f"mock_et_select_del:{et['exam_key']}"
            )])
    if not buttons:
        await cb.answer("O'chiriladigan turlar yo'q (faqat standartlar bor)", show_alert=True)
        return
    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="mock_cancel")])
    await cb.message.edit_text(
        "🗑️ <b>Qaysi turni o'chirmoqchisiz?</b>\n"
        "<i>Standart turlar ko'rsatilmagan</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("mock_et_select_del:"))
async def et_del_confirm(cb: CallbackQuery, state: FSMContext):
    exam_key = cb.data.split(":")[1]
    et = exam_type_ol(exam_key)
    if not et:
        await cb.answer("Topilmadi", show_alert=True)
        return
    await cb.message.edit_text(
        f"⚠️ <b>{et['label']}</b> turini o'chirishni tasdiqlaysizmi?\n"
        f"Bu turning barcha natijalari ham o'chib ketadi!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🗑️ Ha, o'chir", callback_data=f"mock_et_del_ok:{exam_key}"),
            InlineKeyboardButton(text="❌ Yo'q",        callback_data="mock_cancel"),
        ]]),
    )


@router.callback_query(F.data.startswith("mock_et_del_ok:"))
async def et_del_ok(cb: CallbackQuery, state: FSMContext):
    exam_key = cb.data.split(":")[1]
    ok, msg = exam_type_ochir(exam_key)
    icon = "✅" if ok else "❌"
    await cb.message.edit_text(f"{icon} {msg}", parse_mode="HTML")


# ── Exam type yoqish/o'chirish ──────────────────────────────

@router.callback_query(F.data == "mock_et_toggle_list")
async def et_toggle_list(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        "🔄 <b>Qaysi turni yoqish/o'chirish?</b>",
        parse_mode="HTML",
        reply_markup=_exam_list_kb("toggle"),
    )


@router.callback_query(F.data.startswith("mock_et_toggle:"))
async def et_toggle(cb: CallbackQuery, state: FSMContext):
    exam_key = cb.data.split(":")[1]
    et = exam_type_ol(exam_key)
    if not et:
        await cb.answer("Topilmadi", show_alert=True)
        return
    new_state = not et["is_active"]
    exam_type_holat(exam_key, new_state)
    icon = "✅ Yoqildi" if new_state else "❌ O'chirildi"
    await cb.answer(f"{icon}: {et['label']}", show_alert=True)
    # Ro'yxatni yangilash
    await et_toggle_list(cb, state)


# ════════════════════════════════════════════════════════════
# MOCK NATIJA QO'SHISH
# ════════════════════════════════════════════════════════════

@router.message(F.text == "📝 Mock natija qo'shish")
async def mock_natija_start(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    types = exam_types_ol(faqat_aktiv=True)
    if not types:
        await message.answer("❌ Aktiv imtihon turlari yo'q. Avval ⚙️ Mock fanlar boshqaruvi bo'limidan qo'shing.")
        return

    buttons = [[InlineKeyboardButton(
        text=et["label"],
        callback_data=f"mock_et_select:{et['exam_key']}"
    )] for et in types]
    buttons.append([InlineKeyboardButton(text="❌ Bekor", callback_data="mock_cancel")])

    await state.set_state(MockNatijaQosh.exam_key_kutish)
    await message.answer(
        "📝 <b>Imtihon turini tanlang:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("mock_et_select:"), MockNatijaQosh.exam_key_kutish)
async def mock_exam_tanlandi(cb: CallbackQuery, state: FSMContext):
    exam_key = cb.data.split(":")[1]
    et = exam_type_ol(exam_key)
    if not et:
        await cb.answer("Topilmadi", show_alert=True)
        return
    await state.update_data(
        exam_key=exam_key,
        sections={},
        section_idx=0,
    )
    await state.set_state(MockNatijaQosh.talaba_kod_kutish)
    await cb.message.edit_text(
        f"✅ <b>{et['label']}</b> tanlandi.\n\n🔍 O'quvchi <b>kodini</b> kiriting:",
        parse_mode="HTML",
    )


@router.message(MockNatijaQosh.talaba_kod_kutish)
async def mock_talaba_kod(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer("❌ O'quvchi topilmadi. Qayta kiriting:")
        return

    data = await state.get_data()
    et = exam_type_ol(data["exam_key"])
    await state.update_data(talaba_kod=kod, ismlar=talaba["ismlar"])

    # MILLIY_SERT uchun fan nomi so'rash
    if data["exam_key"] == "MILLIY_SERT":
        await state.set_state(MockNatijaQosh.subject_kutish)
        await message.answer(
            f"👤 <b>{talaba['ismlar']}</b>\n\n📚 <b>Fan nomini kiriting:</b>",
            parse_mode="HTML",
        )
        return

    await _ask_schema(message, state, et)


@router.message(MockNatijaQosh.subject_kutish)
async def mock_subject(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    await state.update_data(subject_name=message.text.strip())
    data = await state.get_data()
    et = exam_type_ol(data["exam_key"])
    await _ask_schema(message, state, et)


async def _ask_schema(message: Message, state: FSMContext, et: dict):
    """
    Admin avval qanday section/daraja kiritilishini belgilaydi.
    Format (har qator):
      nom | max
    max ixtiyoriy. Masalan:
      Listening | 9
      Reading | 9
      Speaking | 9
    Faqat bitta section ham bo'lishi mumkin:
      Ball | 100
    """
    await state.update_data(sections={}, section_idx=0, section_defs=[])
    await state.set_state(MockNatijaQosh.schema_kutish)
    label = et.get("label", et.get("exam_key", "Mock"))
    await message.answer(
        f"🧩 <b>{label}</b> uchun <b>nimalar kiritilishini</b> yozing.\n\n"
        "Har qator: <code>nom | max</code> (max ixtiyoriy)\n"
        "Misol:\n"
        "<code>Listening | 9\nReading | 9\nWriting | 9\nSpeaking | 9</code>\n\n"
        "Bitta bo'lim bo'lsa:\n"
        "<code>Ball | 100</code>\n\n"
        "Davom etish uchun yuboring:",
        parse_mode="HTML",
    )


@router.message(MockNatijaQosh.schema_kutish)
async def mock_schema_kiritildi(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    raw_lines = [l.strip() for l in (message.text or "").splitlines() if l.strip()]
    if not raw_lines:
        await message.answer("❌ Kamida 1 ta bo'lim kiriting:")
        return

    section_defs = []
    errors = []
    import re
    for ln in raw_lines:
        parts = [p.strip() for p in ln.split("|")]
        name = parts[0] if parts else ""
        if not name:
            errors.append(f"❌ Bo'sh nom: <code>{ln}</code>")
            continue
        mx = None
        if len(parts) >= 2 and parts[1]:
            try:
                mx = float(parts[1].replace(",", "."))
            except ValueError:
                errors.append(f"❌ Max ball raqam emas: <code>{parts[1]}</code>")
                continue
        key = re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")[:30] or "sec"
        # key collision bo'lmasin
        base = key
        n = 2
        existing = {d["key"] for d in section_defs}
        while key in existing:
            key = f"{base}_{n}"
            n += 1
        section_defs.append({"key": key, "label": name, "max": mx})

    if errors:
        await message.answer("\n".join(errors) + "\n\nQayta kiriting:", parse_mode="HTML")
        return

    await state.update_data(section_defs=section_defs, section_idx=0, sections={})

    # Darajalar ixtiyoriy (admin xohlasa kiritadi)
    await state.set_state(MockNatijaQosh.levels_kutish)
    await message.answer(
        "🎯 <b>Darajalar</b> (ixtiyoriy).\n"
        "Masalan: <code>A1,A2,B1,B2,C1,C2</code>\n"
        "Kerak bo'lmasa <code>-</code> yozing:",
        parse_mode="HTML",
    )


@router.message(MockNatijaQosh.levels_kutish)
async def mock_levels_kiritildi(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    text = (message.text or "").strip()
    if text == "-" or not text:
        await state.update_data(levels_list=None, level=None)
        await _ask_section(message, state)
        return

    levels_list = [l.strip() for l in text.split(",") if l.strip()]
    if not levels_list:
        await message.answer("❌ Darajalar topilmadi. Qayta kiriting yoki <code>-</code>:", parse_mode="HTML")
        return

    await state.update_data(levels_list=levels_list)
    await state.set_state(MockNatijaQosh.level_kutish)
    await message.answer(
        "🎯 <b>Darajani tanlang:</b>",
        parse_mode="HTML",
        reply_markup=_level_kb(levels_list),
    )


async def _ask_section(message: Message, state: FSMContext):
    data = await state.get_data()
    section_defs = data.get("section_defs", [])
    idx = data.get("section_idx", 0)

    if idx >= len(section_defs):
        await _ask_notes(message, state)
        return

    sec = section_defs[idx]
    max_hint = f" (0 – {sec['max']})" if sec.get("max") is not None else ""
    await state.update_data(current_sec_key=sec["key"])
    await state.set_state(MockNatijaQosh.section_kutish)
    await message.answer(
        f"{sec['label']}{max_hint}:",
        parse_mode="HTML",
    )


@router.message(MockNatijaQosh.section_kutish)
async def mock_section_val(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    text = message.text.strip().replace(",", ".")
    try:
        val = float(text)
    except ValueError:
        await message.answer("❌ Raqam kiriting:")
        return

    data = await state.get_data()
    section_defs = data.get("section_defs", [])
    idx = data.get("section_idx", 0)
    sec = section_defs[idx] if idx < len(section_defs) else None

    if sec and sec.get("max") is not None:
        if val < 0 or val > sec["max"]:
            await message.answer(f"❌ Ball 0 – {sec['max']} oralig'ida bo'lishi kerak:")
            return

    key = (sec.get("key") if sec else data.get("current_sec_key", "ball")) if sec else data.get("current_sec_key", "ball")
    label = sec.get("label") if sec else key
    mx = sec.get("max") if sec else None

    # sections qiymatini custom formatda saqlaymiz (label/value/max)
    sections = {
        **data.get("sections", {}),
        key: {"label": label, "value": val, "max": mx},
    }
    await state.update_data(sections=sections, section_idx=idx + 1)
    await _ask_section(message, state)


@router.callback_query(F.data.startswith("mock_level:"), MockNatijaQosh.level_kutish)
async def mock_level(cb: CallbackQuery, state: FSMContext):
    await state.update_data(level=cb.data.split(":")[1])
    await cb.message.delete()
    await _ask_notes(cb.message, state)


async def _ask_notes(message: Message, state: FSMContext):
    await state.set_state(MockNatijaQosh.notes_kutish)
    await message.answer(
        "📝 <b>Izoh</b> (ixtiyoriy, o'tkazish uchun <code>-</code>):",
        parse_mode="HTML",
    )


@router.message(MockNatijaQosh.notes_kutish)
async def mock_notes(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    notes = message.text.strip()
    await state.update_data(notes=None if notes == "-" else notes)
    data = await state.get_data()
    await state.set_state(MockNatijaQosh.tasdiq_kutish)
    await message.answer(
        _build_confirm_text(data) + "\n\n✅ <b>Saqlaysizmi?</b>",
        parse_mode="HTML",
        reply_markup=_tasdiq_kb(),
    )


@router.callback_query(F.data == "mock_save_yes", MockNatijaQosh.tasdiq_kutish)
async def mock_save(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    new_id = mock_natija_qosh(
        talaba_kod=data["talaba_kod"],
        exam_key=data["exam_key"],
        sections=data.get("sections", {}),
        level_label=data.get("level"),
        subject_name=data.get("subject_name"),
        notes=data.get("notes"),
        admin_id=cb.from_user.id,
    )
    # O'quvchiga xabar
    asyncio.create_task(_xabar_talabaga(cb.bot, data["talaba_kod"]))
    et = exam_type_ol(data["exam_key"]) or {}
    await cb.message.edit_text(
        f"✅ <b>Saqlandi!</b> (ID: {new_id})\n"
        f"👤 {data.get('ismlar')} — {et.get('label', data['exam_key'])}",
        parse_mode="HTML",
    )
    await state.clear()


async def _xabar_talabaga(bot, talaba_kod: str):
    try:
        talaba = talaba_topish(talaba_kod)
        if not talaba or not talaba.get("user_id"):
            return
        natijalar = mock_natijalari_ol(talaba_kod, limit=1)
        if not natijalar:
            return
        matn = "✅ <b>Natija chiqdi!</b>\n\n" + format_mock_natija_matn(natijalar[0])
        await bot.send_message(talaba["user_id"], matn, parse_mode="HTML")
    except Exception:
        pass


# ════════════════════════════════════════════════════════════
# MOCK NATIJALARINI KO'RISH (ADMIN)
# ════════════════════════════════════════════════════════════

@router.message(F.text == "📊 Mock natijalarini ko'rish")
async def mock_kor_start(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    await state.set_state(MockNatijaKor.kod_kutish)
    await message.answer("🔍 O'quvchi <b>kodini</b> kiriting:", parse_mode="HTML")


@router.message(MockNatijaKor.kod_kutish)
async def mock_kor_kod(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)
    if not talaba:
        await message.answer("❌ Topilmadi.")
        await state.clear()
        return

    turlari = mock_natija_turlari(kod)
    if not turlari:
        await message.answer(f"👤 <b>{talaba['ismlar']}</b> uchun mock natijalari yo'q.", parse_mode="HTML")
        await state.clear()
        return

    lines = [f"👤 <b>{talaba['ismlar']} ({kod})</b>\n"]
    for t in turlari:
        n = mock_natijalari_ol(kod, exam_key=t["exam_key"], limit=1)
        if n:
            lines.append(format_mock_natija_matn(n[0]))
            lines.append(f"📊 Jami: {t['soni']} ta natija\n────────────────")

    buttons = []
    for t in turlari:
        buttons.append([InlineKeyboardButton(
            text=f"📋 {t['exam_label']} barchasini ko'r ({t['soni']})",
            callback_data=f"mock_admin_all:{kod}:{t['exam_key']}"
        )])
    buttons.append([InlineKeyboardButton(
        text="🗑️ Natija o'chirish",
        callback_data=f"mock_admin_del_ask:{kod}"
    )])

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await state.clear()


@router.callback_query(F.data.startswith("mock_admin_all:"))
async def mock_admin_all(cb: CallbackQuery, state: FSMContext):
    _, kod, exam_key = cb.data.split(":")
    natijalari = mock_natijalari_ol(kod, exam_key=exam_key, limit=15)
    if not natijalari:
        await cb.answer("Topilmadi", show_alert=True)
        return
    et = exam_type_ol(exam_key) or {}
    lines = [f"📋 <b>{et.get('label', exam_key)} — barcha natijalar</b>\n"]
    for i, n in enumerate(natijalari, 1):
        lines.append(f"<b>{i}.</b> " + format_mock_natija_matn(n, et))
        lines.append(f"🆔 ID: {n['id']}\n────────────────")
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n<i>...qolganlar qisqartirildi</i>"
    await cb.message.answer(text, parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data.startswith("mock_admin_del_ask:"))
async def mock_del_ask(cb: CallbackQuery, state: FSMContext):
    kod = cb.data.split(":")[1]
    await state.set_state(MockNatijaOchir.id_kutish)
    await state.update_data(talaba_kod=kod)
    await cb.message.answer(
        "🗑️ O'chirish uchun natija <b>ID raqamini</b> kiriting\n"
        "(ID ni yuqoridagi ro'yxatdan ko'ring):",
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(MockNatijaOchir.id_kutish)
async def mock_del_id(message: Message, state: FSMContext):
    if not await _admin_ok(message, state):
        return
    try:
        natija_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Raqam kiriting.")
        return
    ok = mock_natija_ochir(natija_id)
    if ok:
        await message.answer(f"✅ Natija (ID: {natija_id}) o'chirildi.")
    else:
        await message.answer(f"❌ ID {natija_id} topilmadi.")
    await state.clear()


# ════════════════════════════════════════════════════════════
# BEKOR QILISH
# ════════════════════════════════════════════════════════════

@router.callback_query(F.data == "mock_cancel")
async def mock_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Amal bekor qilindi.")
