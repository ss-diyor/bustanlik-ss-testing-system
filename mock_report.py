"""
Mock imtihon natijalari uchun PDF + PNG hisobot generatori.
pdf_export.py ga parallel, lekin mock natijalariga ixtisoslashgan.

Foydalanish:
    from mock_report import generate_mock_report
    pdf_path, png_path = generate_mock_report(talaba_kod, exam_key)

Qo'llab-quvvatlanadigan imtihon turlari:
    IELTS      — 4 skill (L/R/W/S) + Band score + Overall
    CEFR       — 4 skill + Level badge (A1-C2) + Overall
    SAT        — Reading & Writing + Math + Total /1600
    DTM_MOCK   — Majburiy + Asosiy 1 + Asosiy 2 + Umumiy ball (koeff)
    MILLIY_SERT — Ball + Daraja (A+/A/B+/B/C) + Foiz
    Custom     — JSONB sections dan avtomatik
"""

import os
import json
import re
import unicodedata
from datetime import datetime

from fpdf import FPDF

from database import talaba_topish
from mock_database import mock_natijalari_ol, exam_type_ol
from tz_utils import now as tz_now

# ─── Yo'llar ──────────────────────────────────────────────────────────────────
_BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
_FONT_REG  = os.path.join(_BASE_DIR, "DejaVuSans.ttf")
_FONT_BOLD = os.path.join(_BASE_DIR, "DejaVuSans-Bold.ttf")
_LOGO_PNG  = os.path.join(_BASE_DIR, "logo.png")
_LOGO_PNG  = os.path.join(_BASE_DIR, "logo.png")
_OUT_DIR   = "mock_reports"

if not os.path.exists(_FONT_REG):
    _FONT_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
if not os.path.exists(_FONT_BOLD):
    _FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

os.makedirs(_OUT_DIR, exist_ok=True)

# ─── Ranglar (RGB tuples) ─────────────────────────────────────────────────────
C_NAVY      = (42,  59, 143)   # #2A3B8F — asosiy ko'k rang
C_NAVY_DARK = (28,  40, 100)   # Header + total row ko'yi
C_WHITE     = (255, 255, 255)
C_BLACK     = (30,   30,  30)
C_GRAY_BRD  = (200, 200, 210)  # Border rangi
C_ROW_ALT   = (245, 246, 252)  # Alternativ qator foni
C_ROW_NORM  = (255, 255, 255)  # Oddiy qator foni
C_TEXT      = (55,  55,  85)   # Asosiy matn
C_SCORE     = (28,  40, 100)   # Score raqamlari

CEFR_COLORS = {
    "A1": (200,  50,  50),
    "A2": (220, 100,  30),
    "B1": (200, 155,  20),
    "B2": ( 80, 155,  40),
    "C1": ( 35, 130,  60),
    "C2": ( 20,  95,  40),
}

MILLIY_COLORS = {
    "A+": (185, 140,  20),
    "A":  ( 35, 130,  55),
    "B+": ( 75, 155,  55),
    "B":  (145, 155,  35),
    "C":  (190,  95,  30),
}

# ─── Yordamchi funksiyalar ─────────────────────────────────────────────────────

def _strip_emoji(text: str) -> str:
    """PDF uchun emoji va maxsus belgilarni tozalaydi."""
    if not text:
        return ""
    result = []
    for c in text:
        cat = unicodedata.category(c)
        # So'z harflari, raqamlar, tinish belgilari, bo'sh joy, belgilar
        if cat.startswith(("L", "N", "P", "Z")) or c in " /-+%.,()":
            result.append(c)
    return "".join(result).strip()


def _section_val(sec_val) -> float | None:
    """Section qiymatini float ga aylantiradi."""
    if isinstance(sec_val, dict) and "value" in sec_val:
        v = sec_val["value"]
    else:
        v = sec_val
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _section_max(sec_val, sec_info: dict) -> float | None:
    """Section max qiymatini oladi."""
    if isinstance(sec_val, dict) and "max" in sec_val:
        try:
            return float(sec_val["max"])
        except (TypeError, ValueError):
            pass
    v = sec_info.get("max_score")
    return float(v) if v is not None else None


def _section_label(sec_val, sec_info: dict, fallback: str = "") -> str:
    """Section label (emoji tozalangan)."""
    raw = ""
    if isinstance(sec_val, dict) and "label" in sec_val:
        raw = sec_val["label"]
    elif sec_info.get("label"):
        raw = sec_info["label"]
    else:
        raw = fallback
    return _strip_emoji(raw) or fallback


def _fmt_score(val, decimals=1) -> str:
    """Ballarni formatlash: keraksiz .0 ni olib tashlaydi."""
    if val is None:
        return "—"
    f = round(float(val), decimals)
    if decimals == 0 or f == int(f):
        return str(int(f))
    return str(f)


# ─── FPDF wrapper ─────────────────────────────────────────────────────────────

def _make_pdf() -> FPDF:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("DV",  style="",  fname=_FONT_REG)
    pdf.add_font("DV",  style="B", fname=_FONT_BOLD)
    pdf.set_margins(15, 12, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    return pdf


def _fill(pdf: FPDF, x, y, w, h, color: tuple):
    pdf.set_fill_color(*color)
    pdf.rect(x, y, w, h, style="F")


def _progress_bar(pdf: FPDF, x, y, w, h, value, max_value, bar_color):
    """Foiz ko'rsatkichi (progress bar)."""
    # Kulrang fon
    pdf.set_fill_color(210, 210, 220)
    pdf.rect(x, y, w, h, style="F")
    if max_value and max_value > 0:
        pct = min(1.0, max(0.0, float(value) / float(max_value)))
        fill_w = w * pct
        if fill_w > 0.5:
            pdf.set_fill_color(*bar_color)
            pdf.rect(x, y, fill_w, h, style="F")


# ─── Sahifa bloklari ──────────────────────────────────────────────────────────區

def _draw_header(pdf: FPDF, exam_label: str):
    """Logo + maktab nomi + ko'k sarlavha bloki."""
    PW = pdf.w   # 210mm

    # ── Logo ──────────────────────────────────────────────────
    logo_w = 38
    logo_x = (PW - logo_w) / 2
    logo_y = 10
    logo_exists = False

    for logo_path in (_LOGO_PNG, _LOGO_PNG):
        if os.path.exists(logo_path):
            try:
                pdf.image(logo_path, x=logo_x, y=logo_y, w=logo_w)
                logo_exists = True
                break
            except Exception:
                pass

    logo_bottom = logo_y + (logo_w if logo_exists else 0) + 2

    # ── Ko'k sarlavha paneli ──────────────────────────────────
    bar_y  = logo_bottom + 2
    bar_h  = 20
    _fill(pdf, 0, bar_y, PW, bar_h, C_NAVY_DARK)

    # "MOCK NATIJASI" — kichik subtitle
    pdf.set_xy(0, bar_y + 2.5)
    pdf.set_font("DV", "", 7.5)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(PW, 5, "MOCK NATIJASI", align="C", ln=True)

    # Imtihon nomi — katta sarlavha
    clean_label = _strip_emoji(exam_label).upper()
    pdf.set_font("DV", "B", 14)
    pdf.cell(PW, 7, clean_label, align="C", ln=True)

    pdf.set_y(bar_y + bar_h + 5)
    pdf.set_text_color(*C_BLACK)


def _draw_student_info(pdf: FPDF, talaba: dict):
    """O'quvchi ismi, sinfi, yo'nalishi."""
    sinf     = (talaba.get("sinf") or "").strip()
    yonalish = (talaba.get("yonalish") or talaba.get("yonalishi") or "").strip()
    ismlar   = (talaba.get("ismlar") or "O'quvchi").strip()

    # Ism (ko'k bold)
    pdf.set_font("DV", "B", 12)
    pdf.set_text_color(*C_NAVY)
    pdf.cell(0, 7, f"Hurmatli {ismlar},", align="L", ln=True)

    # Sinf | Yo'nalish
    pdf.set_font("DV", "", 9.5)
    pdf.set_text_color(*C_TEXT)
    meta_parts = []
    if sinf:
        meta_parts.append(f"Sinf: {sinf}")
    if yonalish:
        meta_parts.append(f"Yo'nalish: {yonalish}")
    if meta_parts:
        pdf.cell(0, 5, "   ".join(meta_parts), ln=True)

    pdf.ln(3)
    pdf.set_font("DV", "", 9.5)
    pdf.cell(0, 5, "Quyida sizning mock imtihon natijangiz keltirilgan:", ln=True)
    pdf.ln(4)
    pdf.set_text_color(*C_BLACK)


def _section_row(
    pdf: FPDF, label: str, score_str: str, max_str: str | None = None,
    progress_val=None, progress_max=None, bar_color=None,
    row_bg=None, row_h=12,
):
    """
    Bitta natija satri: [Label]  [Score / Max]
    Ixtiyoriy: pastda progress bar.
    """
    LM = pdf.l_margin
    CW = pdf.w - LM * 2       # content width ≈ 180mm
    LBL_W = CW * 0.60          # 60% label
    SCR_W = CW * 0.40          # 40% score

    x = LM
    y = pdf.get_y()

    # Qator foni
    _fill(pdf, x, y, CW, row_h, row_bg or C_ROW_NORM)

    # Border
    pdf.set_draw_color(*C_GRAY_BRD)
    pdf.rect(x, y, CW, row_h)

    # Label
    pdf.set_xy(x + 3, y + (row_h - 4) / 2)
    pdf.set_font("DV", "", 10)
    pdf.set_text_color(*C_TEXT)
    # Clip label to available width
    pdf.cell(LBL_W - 6, 4, label[:40], align="L")

    # Score text
    scr_text = f"{score_str} / {max_str}" if max_str else score_str
    pdf.set_xy(x + LBL_W, y + (row_h - 4) / 2)
    pdf.set_font("DV", "B", 11)
    pdf.set_text_color(*C_SCORE)
    pdf.cell(SCR_W - 3, 4, scr_text, align="R")

    # Progress bar (2mm tall, at the bottom of the row)
    if progress_val is not None and progress_max:
        bar_x = x + 3
        bar_y = y + row_h - 3
        bar_w = CW - 6
        _progress_bar(
            pdf, bar_x, bar_y, bar_w, 2.0,
            progress_val, progress_max,
            bar_color or C_NAVY
        )

    pdf.set_y(y + row_h)
    pdf.set_text_color(*C_BLACK)


def _total_row(pdf: FPDF, label: str, score_str: str, row_h=15):
    """Ko'k fon, oq matn — Umumiy ball satri."""
    LM = pdf.l_margin
    CW = pdf.w - LM * 2
    LBL_W = CW * 0.55
    SCR_W = CW * 0.45

    x = LM
    y = pdf.get_y()

    _fill(pdf, x, y, CW, row_h, C_NAVY_DARK)
    pdf.set_draw_color(*C_NAVY_DARK)
    pdf.rect(x, y, CW, row_h)

    # Label
    pdf.set_xy(x + 4, y + (row_h - 5) / 2)
    pdf.set_font("DV", "B", 11)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(LBL_W - 4, 5, label, align="L")

    # Score — katta
    pdf.set_xy(x + LBL_W, y + (row_h - 6) / 2)
    pdf.set_font("DV", "B", 14)
    pdf.cell(SCR_W - 4, 6, score_str, align="R")

    pdf.set_y(y + row_h)
    pdf.set_text_color(*C_BLACK)


def _level_badge(pdf: FPDF, level_text: str, badge_color: tuple = None):
    """Daraja badge (markazda, rangli to'rtburchak)."""
    if not level_text:
        return

    color = badge_color or CEFR_COLORS.get(level_text.upper(), C_NAVY)
    badge_w, badge_h = 50, 12
    badge_x = (pdf.w - badge_w) / 2
    badge_y = pdf.get_y() + 3

    _fill(pdf, badge_x, badge_y, badge_w, badge_h, color)
    pdf.set_draw_color(*color)
    pdf.rect(badge_x, badge_y, badge_w, badge_h)

    pdf.set_xy(badge_x, badge_y + 2)
    pdf.set_font("DV", "B", 13)
    pdf.set_text_color(*C_WHITE)
    pdf.cell(badge_w, badge_h - 4, level_text, align="C")

    pdf.set_y(badge_y + badge_h + 5)
    pdf.set_text_color(*C_BLACK)


def _subject_row(pdf: FPDF, subject_name: str):
    """Fan nomi (Milliy sert va boshqalar uchun)."""
    pdf.set_font("DV", "B", 10)
    pdf.set_text_color(*C_NAVY)
    pdf.cell(0, 5, f"Fan: {subject_name}", ln=True)
    pdf.set_text_color(*C_BLACK)
    pdf.ln(2)


def _footer(pdf: FPDF, sana: str, notes: str = None):
    """Sana + izoh + maktab nomi."""
    pdf.ln(6)
    pdf.set_draw_color(*C_GRAY_BRD)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("DV", "", 8.5)
    pdf.set_text_color(*C_TEXT)
    pdf.cell(0, 5, f"Natija sanasi: {sana}", ln=True)

    if notes:
        pdf.cell(0, 5, f"Izoh: {_strip_emoji(notes)}", ln=True)

    pdf.set_font("DV", "", 7.5)
    pdf.cell(
        0, 5,
        f"Hisobot: {tz_now().strftime('%d.%m.%Y %H:%M')}  | @BustanlikSStestingsystembot",
        ln=True,
    )
    pdf.set_text_color(*C_BLACK)


# ─── Imtihon turiga xos rendererlar ───────────────────────────────────────────

def _render_ielts(pdf: FPDF, natija: dict, et: dict):
    sections = natija.get("sections", {})
    sec_map  = {s["section_key"]: s for s in et.get("sections", [])}

    SKILLS = [
        ("listening", "Listening"),
        ("reading",   "Reading"),
        ("writing",   "Writing"),
        ("speaking",  "Speaking"),
    ]

    for i, (key, label) in enumerate(SKILLS):
        if key not in sections:
            continue
        val   = _section_val(sections[key])
        sec   = sec_map.get(key, {})
        max_v = _section_max(sections[key], sec) or 9.0

        _section_row(
            pdf, label,
            score_str   = _fmt_score(val, 1),
            max_str     = _fmt_score(max_v, 1),
            progress_val= val,
            progress_max= max_v,
            bar_color   = (60, 100, 200),
            row_bg      = C_ROW_ALT if i % 2 else C_ROW_NORM,
            row_h       = 13,
        )

    # Overall Band Score
    umumiy = natija.get("umumiy_ball")
    _total_row(
        pdf,
        label     = "Overall Band Score",
        score_str = f"{_fmt_score(umumiy, 1)} / 9.0",
        row_h     = 15,
    )


def _render_cefr(pdf: FPDF, natija: dict, et: dict):
    sections = natija.get("sections", {})
    sec_map  = {s["section_key"]: s for s in et.get("sections", [])}

    SKILLS = [
        ("listening", "Listening"),
        ("reading",   "Reading"),
        ("writing",   "Writing"),
        ("speaking",  "Speaking"),
    ]

    for i, (key, label) in enumerate(SKILLS):
        if key not in sections:
            continue
        val   = _section_val(sections[key])
        sec   = sec_map.get(key, {})
        max_v = _section_max(sections[key], sec) or 75.0

        _section_row(
            pdf, label,
            score_str   = _fmt_score(val, 0),
            max_str     = _fmt_score(max_v, 0),
            progress_val= val,
            progress_max= max_v,
            bar_color   = (50, 140, 70),
            row_bg      = C_ROW_ALT if i % 2 else C_ROW_NORM,
            row_h       = 13,
        )

    # Overall (o'rtacha)
    umumiy = natija.get("umumiy_ball")
    _total_row(
        pdf,
        label     = "Overall Score",
        score_str = f"{_fmt_score(umumiy, 1)} / 75.0",
        row_h     = 15,
    )

    # CEFR Level badge
    level = natija.get("level_label")
    if level:
        pdf.ln(4)
        pdf.set_font("DV", "B", 10)
        pdf.set_text_color(*C_NAVY)
        pdf.cell(0, 5, "CEFR Daraja:", align="C", ln=True)
        badge_color = CEFR_COLORS.get(level.upper(), C_NAVY)
        _level_badge(pdf, level, badge_color)


def _render_sat(pdf: FPDF, natija: dict, et: dict):
    sections = natija.get("sections", {})
    sec_map  = {s["section_key"]: s for s in et.get("sections", [])}

    PARTS = [
        ("reading_writing", "Reading & Writing", 800.0),
        ("math",            "Math",              800.0),
    ]

    for i, (key, label, default_max) in enumerate(PARTS):
        if key not in sections:
            continue
        val   = _section_val(sections[key])
        sec   = sec_map.get(key, {})
        max_v = _section_max(sections[key], sec) or default_max

        _section_row(
            pdf, label,
            score_str   = _fmt_score(val, 0),
            max_str     = _fmt_score(max_v, 0),
            progress_val= val,
            progress_max= max_v,
            bar_color   = (170, 60, 60),
            row_bg      = C_ROW_ALT if i % 2 else C_ROW_NORM,
            row_h       = 13,
        )

    # Total
    umumiy = natija.get("umumiy_ball")
    _total_row(
        pdf,
        label     = "Total Score",
        score_str = f"{_fmt_score(umumiy, 0)} / 1600",
        row_h     = 15,
    )


def _render_dtm_mock(pdf: FPDF, natija: dict, et: dict):
    sections = natija.get("sections", {})
    sec_map  = {s["section_key"]: s for s in et.get("sections", [])}

    PARTS = [
        ("majburiy",  "Majburiy fan",  30.0),
        ("asosiy_1",  "Asosiy fan 1",  30.0),
        ("asosiy_2",  "Asosiy fan 2",  30.0),
    ]

    for i, (key, label, default_max) in enumerate(PARTS):
        if key not in sections:
            continue
        val   = _section_val(sections[key])
        sec   = sec_map.get(key, {})
        max_v = _section_max(sections[key], sec) or default_max

        _section_row(
            pdf, label,
            score_str   = _fmt_score(val, 0),
            max_str     = _fmt_score(max_v, 0),
            progress_val= val,
            progress_max= max_v,
            bar_color   = C_NAVY,
            row_bg      = C_ROW_ALT if i % 2 else C_ROW_NORM,
            row_h       = 13,
        )

    # Umumiy ball (koeffitsient bilan)
    umumiy = natija.get("umumiy_ball")
    _total_row(
        pdf,
        label     = "Umumiy ball",
        score_str = f"{_fmt_score(umumiy, 1)} / 189.0",
        row_h     = 15,
    )


def _render_milliy_sert(pdf: FPDF, natija: dict, et: dict):
    sections = natija.get("sections", {})
    sec_map  = {s["section_key"]: s for s in et.get("sections", [])}

    # Ball (asosan "ball" kaliti, lekin birinchi mavjud qiymat)
    ball_val = None
    ball_key = None
    for key in ("ball",) + tuple(sections.keys()):
        if key in sections:
            v = _section_val(sections[key])
            if v is not None:
                ball_val = v
                ball_key = key
            break

    max_v = None
    if ball_key:
        max_v = _section_max(sections.get(ball_key, {}), sec_map.get(ball_key, {})) or 100.0

    daraja = natija.get("level_label")
    foiz   = ball_val  # /100 bo'lganda foiz = ball

    # Ball satri
    if ball_val is not None:
        _section_row(
            pdf, "Ball",
            score_str   = _fmt_score(ball_val, 1),
            max_str     = _fmt_score(max_v, 0) if max_v else None,
            progress_val= ball_val,
            progress_max= max_v or 100.0,
            bar_color   = (185, 140, 20),
            row_bg      = C_ROW_NORM,
            row_h       = 13,
        )

    # Foiz satri (agar max=100 va ball bevosita foiz bo'lsa)
    if foiz is not None and (max_v is None or max_v == 100.0):
        _section_row(
            pdf, "Foiz",
            score_str   = f"{_fmt_score(foiz, 1)}%",
            max_str     = None,
            row_bg      = C_ROW_ALT,
            row_h       = 12,
        )

    # Daraja satri (total row)
    if daraja:
        badge_color = MILLIY_COLORS.get(daraja.upper(), C_NAVY_DARK)
        _total_row(pdf, "Daraja", daraja, row_h=15)
        # Level badge
        pdf.ln(4)
        _level_badge(pdf, daraja, badge_color)
    elif ball_val is not None:
        _total_row(pdf, "Umumiy ball", _fmt_score(ball_val, 1), row_h=15)


def _render_custom(pdf: FPDF, natija: dict, et: dict):
    """Qo'shimcha (custom) exam types uchun universal renderer."""
    sections = natija.get("sections", {})
    sec_map  = {s["section_key"]: s for s in et.get("sections", [])}

    for i, (key, val_raw) in enumerate(sections.items()):
        val   = _section_val(val_raw)
        sec   = sec_map.get(key, {})
        max_v = _section_max(val_raw, sec)
        label = _section_label(val_raw, sec, fallback=key.replace("_", " ").capitalize())

        _section_row(
            pdf, label,
            score_str   = _fmt_score(val, 1) if val is not None else "—",
            max_str     = _fmt_score(max_v, 1) if max_v is not None else None,
            progress_val= val if max_v else None,
            progress_max= max_v,
            bar_color   = C_NAVY,
            row_bg      = C_ROW_ALT if i % 2 else C_ROW_NORM,
            row_h       = 13,
        )

    # Umumiy ball
    umumiy  = natija.get("umumiy_ball")
    et_max  = et.get("total_max")
    if umumiy is not None:
        total_str = (
            f"{_fmt_score(umumiy, 1)} / {_fmt_score(et_max, 1)}"
            if et_max else _fmt_score(umumiy, 1)
        )
        _total_row(pdf, "Umumiy ball", total_str, row_h=15)

    # Level badge (CEFR-style, agar mavjud bo'lsa)
    level = natija.get("level_label")
    if level:
        pdf.ln(4)
        _level_badge(pdf, level)


# ─── Renderer ro'yxati ─────────────────────────────────────────────────────────
_RENDERERS = {
    "IELTS":       _render_ielts,
    "CEFR":        _render_cefr,
    "SAT":         _render_sat,
    "DTM_MOCK":    _render_dtm_mock,
    "MILLIY_SERT": _render_milliy_sert,
}


# ─── Asosiy funksiya ───────────────────────────────────────────────────────────

def generate_mock_report(
    talaba_kod: str,
    exam_key: str = None,
    natija_id: int = None,
) -> tuple:
    """
    Bitta mock natijasi uchun PDF va PNG fayllarni yaratadi.

    Parametrlar:
        talaba_kod  — o'quvchi kodi
        exam_key    — imtihon turi (IELTS, CEFR, DTM_MOCK, ...)
        natija_id   — muayyan natija ID (None bo'lsa — eng oxirgisi)

    Qaytaradi:
        (pdf_path, png_path) — muvaffaqiyatli
        (None, None)         — xatolik yuz berganda
    """
    # ── Ma'lumotlarni olish ────────────────────────────────────
    talaba = talaba_topish(talaba_kod)
    if not talaba:
        return None, None

    if natija_id:
        from database import get_connection, release_connection
        import psycopg2.extras
        conn = get_connection()
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM mock_natijalari WHERE id = %s", (natija_id,))
            row = cur.fetchone()
            cur.close()
        finally:
            release_connection(conn)

        if not row:
            return None, None
        natija = dict(row)
        if isinstance(natija.get("sections"), str):
            natija["sections"] = json.loads(natija["sections"])
        exam_key = natija["exam_key"]
    else:
        natijalari = mock_natijalari_ol(talaba_kod, exam_key=exam_key, limit=1)
        if not natijalari:
            return None, None
        natija   = natijalari[0]
        exam_key = natija["exam_key"]

    et          = exam_type_ol(exam_key) or {}
    exam_label  = natija.get("exam_label") or et.get("label", exam_key)
    sana        = str(natija.get("test_sanasi", ""))[:10]
    subject     = natija.get("subject_name")
    notes       = natija.get("notes")

    # ── PDF yaratish ────────────────────────────────────────────
    pdf = _make_pdf()
    pdf.add_page()

    _draw_header(pdf, exam_label)
    _draw_student_info(pdf, talaba)

    if subject:
        _subject_row(pdf, _strip_emoji(subject))

    renderer = _RENDERERS.get(exam_key, _render_custom)
    renderer(pdf, natija, et)

    _footer(pdf, sana, notes)

    # ── Fayllarni saqlash ───────────────────────────────────────
    safe_key  = re.sub(r"[^A-Za-z0-9_]", "_", exam_key)
    timestamp = tz_now().strftime("%Y%m%d_%H%M%S")
    pdf_path  = os.path.join(_OUT_DIR, f"mock_{talaba_kod}_{safe_key}_{timestamp}.pdf")

    pdf.output(pdf_path)

    # ── PDF → PNG (pymupdf) ─────────────────────────────────────
    png_path = pdf_path.replace(".pdf", ".png")
    try:
        import fitz  # PyMuPDF
        doc  = fitz.open(pdf_path)
        page = doc[0]
        # 2.5x zoom: ~1488px kenglik — Telegram uchun qulay
        mat  = fitz.Matrix(2.5, 2.5)
        pix  = page.get_pixmap(matrix=mat, alpha=False)
        pix.save(png_path)
        doc.close()
    except Exception:
        import traceback
        traceback.print_exc()
        png_path = None

    return pdf_path, png_path


def generate_all_mock_reports(talaba_kod: str) -> list:
    """
    O'quvchining BARCHA imtihon turlaridan oxirgi natijalar uchun hisobotlar.

    Qaytaradi: [(exam_key, pdf_path, png_path), ...]
    """
    from mock_database import mock_natija_turlari
    turlari = mock_natija_turlari(talaba_kod)
    results = []
    for t in turlari:
        key = t.get("exam_key")
        pdf_path, png_path = generate_mock_report(talaba_kod, exam_key=key)
        if pdf_path:
            results.append((key, pdf_path, png_path))
    return results
