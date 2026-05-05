"""
Google Sheets Eksport moduli.
Ma'lumotlarni Google Sheets ga yuklaydi.

Environment variables:
    GOOGLE_CREDENTIALS_JSON  — service account JSON (to'liq matn yoki base64)
    GOOGLE_SHEETS_ID         — Google Sheets hujjat ID si
"""

import os
import json
import base64
import logging
from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials
from tz_utils import now as tz_now
from database import (
    get_all_students_for_excel,
    maktab_statistikasi,
    maktablar_ol,
    sinf_ol,
    get_all_in_class,
    talaba_topish,
    talaba_natijalari,
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# ── Uslub konstantalar (RGB hex) ────────────────────────────────────────────
HEADER_BG    = {"red": 0.12, "green": 0.31, "blue": 0.47}   # #1F4E79
SUBHEAD_BG   = {"red": 0.18, "green": 0.46, "blue": 0.71}   # #2E75B6
ALT_ROW_BG   = {"red": 0.84, "green": 0.89, "blue": 0.94}   # #D6E4F0
TOTAL_BG     = {"red": 0.74, "green": 0.84, "blue": 0.94}   # #BDD7EE
WHITE_FG     = {"red": 1.0,  "green": 1.0,  "blue": 1.0}
DARK_FG      = {"red": 0.08, "green": 0.08, "blue": 0.08}


def _load_credentials() -> Optional[Credentials]:
    """Railway environment dan service account credentials yuklaydi."""
    raw = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    if not raw:
        raise ValueError(
            "GOOGLE_CREDENTIALS_JSON environment variable topilmadi. "
            "Railway Variables da to'g'ri sozlang."
        )
    # Base64 encoded bo'lishi mumkin
    try:
        decoded = base64.b64decode(raw).decode("utf-8")
        info = json.loads(decoded)
    except Exception:
        # To'g'ridan-to'g'ri JSON matn
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "GOOGLE_CREDENTIALS_JSON noto'g'ri format. "
                "To'liq JSON yoki base64 encoded JSON bo'lishi kerak."
            ) from exc

    return Credentials.from_service_account_info(info, scopes=SCOPES)


def _get_sheet_id() -> str:
    sheet_id = os.getenv("GOOGLE_SHEETS_ID", "").strip()
    if not sheet_id:
        raise ValueError(
            "GOOGLE_SHEETS_ID environment variable topilmadi. "
            "Railway Variables da to'g'ri sozlang."
        )
    return sheet_id


def _get_client() -> gspread.Client:
    creds = _load_credentials()
    return gspread.authorize(creds)


def _open_spreadsheet() -> gspread.Spreadsheet:
    client = _get_client()
    sheet_id = _get_sheet_id()
    return client.open_by_key(sheet_id)


def _ensure_worksheet(
    spreadsheet: gspread.Spreadsheet,
    title: str,
    rows: int = 1000,
    cols: int = 20,
) -> gspread.Worksheet:
    """Varaq mavjud bo'lsa ochadi, bo'lmasa yaratadi va tozalaydi."""
    try:
        ws = spreadsheet.worksheet(title)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)
    return ws


def _fmt_header(ws: gspread.Worksheet, row: int, col_count: int):
    """Header qatorni uslublantiradi."""
    ws.format(
        f"A{row}:{_col_letter(col_count)}{row}",
        {
            "backgroundColor": HEADER_BG,
            "textFormat": {
                "foregroundColor": WHITE_FG,
                "bold": True,
                "fontSize": 11,
            },
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
        },
    )


def _fmt_title(ws: gspread.Worksheet, row: int, col_count: int):
    """Sarlavha qatorni uslublantiradi."""
    ws.format(
        f"A{row}:{_col_letter(col_count)}{row}",
        {
            "backgroundColor": {"red": 1, "green": 1, "blue": 1},
            "textFormat": {
                "foregroundColor": HEADER_BG,
                "bold": True,
                "fontSize": 14,
            },
            "horizontalAlignment": "CENTER",
        },
    )


def _fmt_total(ws: gspread.Worksheet, row: int, col_count: int):
    """Jami qatorni uslublantiradi."""
    ws.format(
        f"A{row}:{_col_letter(col_count)}{row}",
        {
            "backgroundColor": TOTAL_BG,
            "textFormat": {"bold": True, "fontSize": 10},
            "horizontalAlignment": "CENTER",
        },
    )


def _fmt_alt_rows(ws: gspread.Worksheet, start: int, end: int, col_count: int):
    """Juft qatorlarni ranglaydi."""
    for r in range(start, end + 1):
        if (r - start) % 2 == 1:
            ws.format(
                f"A{r}:{_col_letter(col_count)}{r}",
                {"backgroundColor": ALT_ROW_BG},
            )


def _fmt_footer(ws: gspread.Worksheet, row: int):
    ws.format(
        f"A{row}",
        {
            "textFormat": {
                "italic": True,
                "fontSize": 9,
                "foregroundColor": {"red": 0.35, "green": 0.35, "blue": 0.35},
            }
        },
    )


def _col_letter(n: int) -> str:
    """1 → A, 26 → Z, 27 → AA ..."""
    result = ""
    while n:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


# ════════════════════════════════════════════════════════════════════
# 1. Barcha o'quvchilar va natijalar
# ════════════════════════════════════════════════════════════════════

def export_all_students(tab_title: str = "Barcha o'quvchilar") -> str:
    """Barcha o'quvchilar va ularning so'nggi natijalarini eksport qiladi."""
    students = get_all_students_for_excel()
    if not students:
        return "❌ Ma'lumot topilmadi."

    spreadsheet = _open_spreadsheet()
    ws = _ensure_worksheet(spreadsheet, tab_title, rows=len(students) + 10, cols=9)

    now_str = tz_now().strftime("%d.%m.%Y %H:%M")
    headers = [
        "Kod", "Ism Familiya", "Maktab", "Sinf",
        "Yo'nalish", "Majburiy", "Asosiy 1", "Asosiy 2", "Umumiy ball",
    ]
    col_count = len(headers)

    # 1-qator: sarlavha
    ws.update("A1", [[f"Barcha o'quvchilar — {now_str}"]])
    ws.merge_cells(f"A1:{_col_letter(col_count)}1")
    _fmt_title(ws, 1, col_count)

    # 2-qator: ustun nomlari
    ws.update("A2", [headers])
    _fmt_header(ws, 2, col_count)

    # Ma'lumotlar
    rows = []
    for s in students:
        rows.append([
            s.get("kod", ""),
            s.get("ismlar", ""),
            s.get("maktab_nomi", ""),
            s.get("sinf", ""),
            s.get("yonalish") or "—",
            s.get("majburiy", 0),
            s.get("asosiy_1", 0),
            s.get("asosiy_2", 0),
            s.get("umumiy_ball", 0),
        ])

    if rows:
        ws.update(f"A3", rows)
        _fmt_alt_rows(ws, 3, 2 + len(rows), col_count)

    _fmt_footer(ws, len(rows) + 4)
    ws.update(f"A{len(rows) + 4}", [[f"Hisobot sanasi: {now_str}"]])

    url = f"https://docs.google.com/spreadsheets/d/{_get_sheet_id()}"
    logger.info("Google Sheets eksport: barcha o'quvchilar (%d ta)", len(rows))
    return url


# ════════════════════════════════════════════════════════════════════
# 2. Maktab statistikasi
# ════════════════════════════════════════════════════════════════════

def export_maktab_statistika(
    maktab_id: Optional[int] = None,
    tab_title: str = "Maktab statistikasi",
) -> str:
    stats = maktab_statistikasi(maktab_id)
    if not stats:
        return "❌ Statistika topilmadi."

    if maktab_id:
        maktablar = maktablar_ol()
        maktab = next((m for m in maktablar if m["id"] == maktab_id), None)
        title_text = f"{maktab['nomi'] if maktab else 'Maktab'} statistikasi"
        tab_title = (maktab["nomi"][:25] if maktab else "Maktab") + " stat"
    else:
        title_text = "Barcha maktablar statistikasi"

    spreadsheet = _open_spreadsheet()
    ws = _ensure_worksheet(spreadsheet, tab_title, rows=len(stats) + 10, cols=6)

    now_str = tz_now().strftime("%d.%m.%Y %H:%M")
    headers = ["Maktab", "Sinf", "O'quvchilar", "O'rtacha", "Eng yuqori", "Eng past"]
    col_count = len(headers)

    ws.update("A1", [[f"{title_text} — {now_str}"]])
    ws.merge_cells(f"A1:{_col_letter(col_count)}1")
    _fmt_title(ws, 1, col_count)

    ws.update("A2", [headers])
    _fmt_header(ws, 2, col_count)

    rows = []
    jami = 0
    for s in stats:
        rows.append([
            s.get("maktab_nomi", ""),
            s.get("sinf", ""),
            s.get("oquvchilar_soni", 0),
            round(s.get("ortacha_ball", 0), 1),
            round(s.get("eng_yuqori_ball", 0), 1),
            round(s.get("eng_past_ball", 0), 1),
        ])
        jami += s.get("oquvchilar_soni", 0)

    if rows:
        ws.update("A3", rows)
        _fmt_alt_rows(ws, 3, 2 + len(rows), col_count)

    total_row = len(rows) + 3
    ws.update(f"A{total_row}", [[f"JAMI O'QUVCHILAR", "", jami, "", "", ""]])
    _fmt_total(ws, total_row, col_count)

    ws.update(f"A{total_row + 2}", [[f"Hisobot sanasi: {now_str}"]])
    _fmt_footer(ws, total_row + 2)

    url = f"https://docs.google.com/spreadsheets/d/{_get_sheet_id()}"
    logger.info("Google Sheets eksport: maktab statistikasi (%d qator)", len(rows))
    return url


# ════════════════════════════════════════════════════════════════════
# 3. Sinf reytingi
# ════════════════════════════════════════════════════════════════════

def export_sinf_reyting(
    sinf: Optional[str] = None,
    maktab_id: Optional[int] = None,
    tab_title: str = "Sinf reytingi",
) -> str:
    if sinf:
        sinflar = [sinf]
        title_text = f"{sinf} sinf reytingi"
        tab_title = f"{sinf} reyting"
    elif maktab_id:
        from database import sinf_ol_batafsil
        batafsil = sinf_ol_batafsil()
        maktablar_l = maktablar_ol()
        maktab = next((m for m in maktablar_l if m["id"] == maktab_id), None)
        maktab_nomi = maktab["nomi"] if maktab else "Maktab"
        sinflar = [
            s["nomi"] for s in batafsil if s["maktab_id"] == maktab_id
        ]
        title_text = f"{maktab_nomi} — barcha sinflar reytingi"
        tab_title = maktab_nomi[:25] + " reyting"
    else:
        sinflar = sinf_ol()
        title_text = "Barcha sinflar reytingi"

    if not sinflar:
        return "❌ Sinflar topilmadi."

    # Barcha ma'lumotlarni yig'amiz
    all_rows = []
    for sinf_name in sinflar:
        talabalar = get_all_in_class(sinf_name)
        for i, t in enumerate(talabalar or [], 1):
            all_rows.append([
                len(all_rows) + 1,
                sinf_name,
                t.get("ismlar", ""),
                t.get("kod", ""),
                t.get("yonalish") or "—",
                t.get("umumiy_ball", 0),
            ])

    if not all_rows:
        return "❌ Ma'lumot topilmadi."

    spreadsheet = _open_spreadsheet()
    ws = _ensure_worksheet(spreadsheet, tab_title, rows=len(all_rows) + 10, cols=6)

    now_str = tz_now().strftime("%d.%m.%Y %H:%M")
    headers = ["№", "Sinf", "Ism Familiya", "Kod", "Yo'nalish", "Ball"]
    col_count = len(headers)

    ws.update("A1", [[f"{title_text} — {now_str}"]])
    ws.merge_cells(f"A1:{_col_letter(col_count)}1")
    _fmt_title(ws, 1, col_count)

    ws.update("A2", [headers])
    _fmt_header(ws, 2, col_count)

    ws.update("A3", all_rows)
    _fmt_alt_rows(ws, 3, 2 + len(all_rows), col_count)

    footer_row = len(all_rows) + 4
    ws.update(f"A{footer_row}", [[f"Hisobot sanasi: {now_str}"]])
    _fmt_footer(ws, footer_row)

    url = f"https://docs.google.com/spreadsheets/d/{_get_sheet_id()}"
    logger.info("Google Sheets eksport: sinf reytingi (%d ta o'quvchi)", len(all_rows))
    return url


# ════════════════════════════════════════════════════════════════════
# 4. Bitta o'quvchi tarixi
# ════════════════════════════════════════════════════════════════════

def export_student_history(
    talaba_kod: str,
    tab_title: str = None,
) -> str:
    talaba = talaba_topish(talaba_kod)
    if not talaba:
        return f"❌ {talaba_kod} kodli o'quvchi topilmadi."

    natijalar = talaba_natijalari(talaba_kod) or []
    tab = tab_title or f"{talaba_kod} tarixi"

    spreadsheet = _open_spreadsheet()
    ws = _ensure_worksheet(spreadsheet, tab[:31], rows=len(natijalar) + 15, cols=5)

    now_str = tz_now().strftime("%d.%m.%Y %H:%M")
    col_count = 5

    ws.update("A1", [[f"O'quvchi hisoboti — {talaba['ismlar']}"]])
    ws.merge_cells(f"A1:{_col_letter(col_count)}1")
    _fmt_title(ws, 1, col_count)

    # Ma'lumot bloki
    info = [
        ["Kod",       talaba["kod"],                    "", "", ""],
        ["Sinf",      talaba["sinf"],                   "", "", ""],
        ["Yo'nalish", talaba.get("yonalish") or "—",    "", "", ""],
    ]
    ws.update("A2", info)
    ws.format("A2:A4", {
        "backgroundColor": SUBHEAD_BG,
        "textFormat": {"foregroundColor": WHITE_FG, "bold": True},
    })

    # Natijalar jadvali
    ws.update("A5", [["Sana", "Majburiy", "Asosiy 1", "Asosiy 2", "Umumiy ball"]])
    _fmt_header(ws, 5, col_count)

    if natijalar:
        rows = []
        for n in natijalar:
            sana = n["test_sanasi"]
            if hasattr(sana, "strftime"):
                sana = sana.strftime("%d.%m.%Y")
            rows.append([sana, n["majburiy"], n["asosiy_1"], n["asosiy_2"], n["umumiy_ball"]])

        ws.update("A6", rows)
        _fmt_alt_rows(ws, 6, 5 + len(rows), col_count)

        # Statistika
        stat_row = 6 + len(rows) + 1
        avg = sum(n["umumiy_ball"] for n in natijalar) / len(natijalar)
        mx  = max(n["umumiy_ball"] for n in natijalar)
        mn  = min(n["umumiy_ball"] for n in natijalar)

        stats = [
            ["O'rtacha ball", f"{avg:.1f}", "", "", ""],
            ["Eng yuqori",    mx,           "", "", ""],
            ["Eng past",      mn,           "", "", ""],
            ["Jami testlar",  f"{len(natijalar)} ta", "", "", ""],
        ]
        ws.update(f"A{stat_row}", stats)
        ws.format(f"A{stat_row}:A{stat_row + 3}", {
            "backgroundColor": TOTAL_BG,
            "textFormat": {"bold": True},
        })
        footer_row = stat_row + len(stats) + 1
    else:
        ws.update("A6", [["Natijalar mavjud emas"]])
        footer_row = 8

    ws.update(f"A{footer_row}", [[f"Hisobot sanasi: {now_str}"]])
    _fmt_footer(ws, footer_row)

    url = f"https://docs.google.com/spreadsheets/d/{_get_sheet_id()}"
    logger.info("Google Sheets eksport: o'quvchi %s tarixi", talaba_kod)
    return url
