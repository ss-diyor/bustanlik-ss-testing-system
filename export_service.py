"""
export_service.py
------------------
O'quvchining barcha natijalari uchun:
  - Har bir mock uchun PDF hisobot (mavjud mock_report.py generatori orqali)
  - Umumiy Excel jadval (Mock, Asosiy DTM, Mini-testlar, Profil)
  - Hammasini ZIP arxivga jamlash

Eslatma: loyihaning qolgan qismi psycopg2 (sinxron) orqali ishlaydi —
bu modul ham shu uslubga mos. Chaqiruvchi tomon (masalan export.py)
bloklovchi funksiyalarni `loop.run_in_executor(None, ...)` orqali
chaqirishi kerak.
"""

import io
import os
import zipfile
from datetime import datetime

import psycopg2.extras
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

from database import get_connection, release_connection, talaba_topish, talaba_topish_user_id
from mock_database import mock_natijalari_ol
from mock_report import generate_mock_report


# ─────────────────────────────────────────────────
#  DB dan ma'lumot olish
# ─────────────────────────────────────────────────

def _collect_data(talaba: dict) -> dict:
    """Berilgan o'quvchi (talaba) uchun barcha natijalarni yig'adi."""
    if not talaba:
        return {}

    kod = talaba["kod"]

    mock_results = mock_natijalari_ol(kod, limit=200)

    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Asosiy DTM simulyatsiyasi natijalari (majburiy + asosiy fanlar)
        cur.execute(
            """
            SELECT majburiy, asosiy_1, asosiy_2, umumiy_ball, test_sanasi
            FROM test_natijalari
            WHERE talaba_kod = %s
            ORDER BY test_sanasi DESC
            """,
            (kod,),
        )
        dtm_results = [dict(r) for r in cur.fetchall()]

        # Mini-testlar (fan nomi bilan birga, mini_testlar jadvali orqali)
        cur.execute(
            """
            SELECT mt.nomi AS test_nomi, mt.fan AS fan,
                   r.ball, r.jami_savol, r.sana
            FROM mini_test_natijalari r
            LEFT JOIN mini_testlar mt ON mt.id = r.test_id
            WHERE r.talaba_kod = %s
            ORDER BY r.sana DESC
            LIMIT 100
            """,
            (kod,),
        )
        mini_results = [dict(r) for r in cur.fetchall()]
        cur.close()
    finally:
        release_connection(conn)

    return {
        "student": talaba,
        "mock_results": mock_results,
        "dtm_results": dtm_results,
        "mini_results": mini_results,
    }


def fetch_student_data(user_id: int) -> dict:
    """O'quvchining (telegram user_id bo'yicha) barcha natijalarini oladi."""
    talaba = talaba_topish_user_id(user_id)
    return _collect_data(talaba)


def fetch_student_data_by_kod(kod: str) -> dict:
    """O'quvchining (kod bo'yicha, admin panel uchun) barcha natijalarini oladi."""
    talaba = talaba_topish(kod.strip().upper())
    return _collect_data(talaba)


# ─────────────────────────────────────────────────
#  Excel — barcha natijalar jadvali
# ─────────────────────────────────────────────────

def _xl_header_style() -> tuple:
    font = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
    fill = PatternFill("solid", fgColor="1E3A8A")
    align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    return font, fill, align


def _xl_border() -> Border:
    thin = Side(style="thin", color="CBD5E1")
    return Border(left=thin, right=thin, top=thin, bottom=thin)


def _sections_to_str(sections) -> str:
    """Sections JSONB obyektini o'qish uchun qulay matnga aylantiradi."""
    if not sections or not isinstance(sections, dict):
        return ""
    parts = []
    for key, val in sections.items():
        if isinstance(val, dict):
            v = val.get("value", val.get("score", val.get("ball", "")))
        else:
            v = val
        parts.append(f"{key}: {v}")
    return "; ".join(parts)


def _write_header_row(ws, headers, widths, h_font, h_fill, h_align, border):
    for col, (h, w) in enumerate(zip(headers, widths), 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = h_font
        cell.fill = h_fill
        cell.alignment = h_align
        cell.border = border
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.row_dimensions[1].height = 28


def generate_excel(data: dict) -> bytes:
    """Barcha natijalar uchun Excel fayl hosil qiladi."""
    wb = Workbook()
    student = data["student"]
    h_font, h_fill, h_align = _xl_header_style()
    border = _xl_border()

    # ── 1-varaq: Mock natijalari ──────────────────
    ws1 = wb.active
    ws1.title = "Mock natijalari"
    headers1 = ["Sana", "Imtihon turi", "Fan", "Umumiy ball", "Daraja", "Sektsiyalar", "Izoh"]
    widths1 = [16, 20, 16, 12, 14, 40, 24]
    _write_header_row(ws1, headers1, widths1, h_font, h_fill, h_align, border)

    for row_i, r in enumerate(data["mock_results"], 2):
        row_data = [
            r["test_sanasi"].strftime("%d.%m.%Y %H:%M") if r.get("test_sanasi") else "",
            r.get("exam_label") or r.get("exam_key", ""),
            r.get("subject_name", "") or "",
            r.get("umumiy_ball", ""),
            r.get("level_label", "") or "",
            _sections_to_str(r.get("sections")),
            r.get("notes", "") or "",
        ]
        bg = "F0F9FF" if row_i % 2 == 0 else "FFFFFF"
        for col, val in enumerate(row_data, 1):
            cell = ws1.cell(row=row_i, column=col, value=val)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.fill = PatternFill("solid", fgColor=bg)
            cell.border = border

    # ── 2-varaq: Asosiy DTM natijalari ────────────
    ws2 = wb.create_sheet("Asosiy DTM")
    headers2 = ["Sana", "Majburiy", "Asosiy-1", "Asosiy-2", "Umumiy ball"]
    widths2 = [16, 12, 12, 12, 14]
    _write_header_row(ws2, headers2, widths2, h_font, h_fill, h_align, border)

    for row_i, r in enumerate(data["dtm_results"], 2):
        row_data = [
            r["test_sanasi"].strftime("%d.%m.%Y %H:%M") if r.get("test_sanasi") else "",
            r.get("majburiy", ""),
            r.get("asosiy_1", ""),
            r.get("asosiy_2", ""),
            r.get("umumiy_ball", ""),
        ]
        bg = "FFF7ED" if row_i % 2 == 0 else "FFFFFF"
        for col, val in enumerate(row_data, 1):
            cell = ws2.cell(row=row_i, column=col, value=val)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.fill = PatternFill("solid", fgColor=bg)
            cell.border = border

    # ── 3-varaq: Mini-test natijalari ─────────────
    ws3 = wb.create_sheet("Mini-testlar")
    headers3 = ["Sana", "Test nomi", "Fan", "Ball", "Jami savol", "Foiz (%)"]
    widths3 = [16, 22, 16, 10, 12, 12]
    _write_header_row(ws3, headers3, widths3, h_font, h_fill, h_align, border)

    for row_i, r in enumerate(data["mini_results"], 2):
        ball = r.get("ball")
        jami = r.get("jami_savol")
        foiz = round((ball / jami) * 100, 1) if ball is not None and jami else ""
        row_data = [
            r["sana"].strftime("%d.%m.%Y %H:%M") if r.get("sana") else "",
            r.get("test_nomi", "") or "",
            r.get("fan", "") or "",
            ball if ball is not None else "",
            jami if jami is not None else "",
            foiz,
        ]
        bg = "F0FDF4" if row_i % 2 == 0 else "FFFFFF"
        for col, val in enumerate(row_data, 1):
            cell = ws3.cell(row=row_i, column=col, value=val)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.fill = PatternFill("solid", fgColor=bg)
            cell.border = border

    # ── 4-varaq: O'quvchi ma'lumoti ───────────────
    ws4 = wb.create_sheet("Profil")
    registered = student.get("registered_at")
    info = [
        ("Ism Familiya", student.get("ismlar", "")),
        ("Kod", student.get("kod", "")),
        ("Sinf", student.get("sinf", "")),
        ("Yo'nalish", student.get("yonalish", "")),
        ("Maktab", student.get("maktab_nomi", "") or ""),
        ("Ro'yxatdan o'tgan", registered.strftime("%d.%m.%Y") if hasattr(registered, "strftime") else ""),
        ("Jami mock natijalar", len(data["mock_results"])),
        ("Jami asosiy DTM natijalar", len(data["dtm_results"])),
        ("Jami mini-testlar", len(data["mini_results"])),
        ("Hisobot sanasi", datetime.now().strftime("%d.%m.%Y %H:%M")),
    ]
    ws4.column_dimensions["A"].width = 26
    ws4.column_dimensions["B"].width = 30

    for row_i, (label, value) in enumerate(info, 1):
        a = ws4.cell(row=row_i, column=1, value=label)
        b = ws4.cell(row=row_i, column=2, value=value)
        a.font = Font(bold=True, color="1E3A8A")
        a.fill = PatternFill("solid", fgColor="EFF6FF")
        a.border = border
        b.border = border
        a.alignment = Alignment(vertical="center")
        b.alignment = Alignment(vertical="center")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────────────────────────────────────
#  ZIP — hammasini jamlash
# ─────────────────────────────────────────────────

def build_zip_archive(data: dict) -> io.BytesIO:
    """
    Excel + har bir mock uchun PDF hisobotlarni bitta ZIP arxivga yig'adi.
    Mock PDF-lar mavjud mock_report.generate_mock_report() orqali hosil
    qilinadi (IELTS/CEFR/SAT/DTM/Milliy sertifikat uchun mos shablonlar bilan).

    Qaytaradi: BytesIO ob'ekti (Telegram uchun tayyor)
    """
    student = data["student"]
    kod = student["kod"]
    safe_name = (student.get("ismlar") or kod or "talaba").replace(" ", "_")
    date_str = datetime.now().strftime("%Y%m%d")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:

        # Excel jadval
        excel_bytes = generate_excel(data)
        zf.writestr(f"{safe_name}_natijalar_{date_str}.xlsx", excel_bytes)

        # Har bir mock uchun alohida PDF (mavjud generatordan foydalanadi)
        for result in data["mock_results"]:
            natija_id = result.get("id")
            if not natija_id:
                continue
            try:
                pdf_path, png_path = generate_mock_report(kod, natija_id=natija_id)
            except Exception:
                pdf_path, png_path = None, None

            if not pdf_path or not os.path.exists(pdf_path):
                continue

            exam_key = (result.get("exam_key") or "exam").replace(" ", "_")
            exam_date = (
                result["test_sanasi"].strftime("%Y%m%d")
                if result.get("test_sanasi") else str(natija_id)
            )
            try:
                with open(pdf_path, "rb") as f:
                    zf.writestr(f"pdf/{exam_key}_{exam_date}.pdf", f.read())
            finally:
                # Vaqtinchalik fayllarni tozalash (disk to'lib qolmasligi uchun)
                for p in (pdf_path, png_path):
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass

        # README.txt
        readme = (
            f"Bustanlik SS Testing System — Natijalar arxivi\n"
            f"{'=' * 50}\n\n"
            f"O'quvchi : {student.get('ismlar', '—')}\n"
            f"Kod      : {kod}\n"
            f"Sinf     : {student.get('sinf', '—')}\n"
            f"Yo'nalish: {student.get('yonalish', '—')}\n"
            f"Sana     : {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Tarkib:\n"
            f"  /{safe_name}_natijalar_{date_str}.xlsx  — barcha natijalar jadvali\n"
            f"  /pdf/  — har bir mock uchun alohida PDF hisobot\n"
        )
        zf.writestr("README.txt", readme.encode("utf-8"))

    zip_buf.seek(0)
    return zip_buf
