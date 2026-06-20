"""
sheets_import.py — Google Sheets'dan teskari import (Sheets → Database).

sheets_export.py "Barcha o'quvchilar" varag'iga ma'lumotlarni yozadi.
Admin o'sha varaqda ballarni to'g'ridan-to'g'ri Google Sheets ichida
tahrirlashi mumkin (masalan telefon yoki noutbukda, Excel'siz).
Bu modul o'sha varaqni o'qib, DB bilan solishtiradi va faqat
FARQ qilgan qatorlarni yangilaydi.

Ishlash tartibi (xavfsizlik uchun ikki bosqichli):
    1. preview_sheet_changes()  — hech narsani o'zgartirmaydi, faqat
       qaysi o'quvchilar yangilanishi kerakligini aniqlaydi (dry-run).
    2. apply_sheet_changes()    — admin tasdiqlagandan keyin haqiqiy
       yozuvni amalga oshiradi.

Ustun tartibi (sheets_export.py dagi export_all_students() bilan bir xil):
    A: Kod | B: Ism Familiya | C: Maktab | D: Sinf | E: Yo'nalish
    F: Majburiy | G: Asosiy 1 | H: Asosiy 2 | I: Umumiy ball (avtomatik hisoblanadi)

Eslatma: Kod, Ism, Maktab, Sinf, Yo'nalish ustunlari faqat o'qish uchun —
ular orqali yangi o'quvchi YARATILMAYDI va talaba ma'lumotlari
o'zgartirilmaydi (xavfsizlik). Faqat F/G/H (ball) ustunlaridagi
farqlar import qilinadi.
"""

import logging
from typing import Optional

import gspread

from database import talaba_topish, talaba_songi_natija, natija_qosh
from sheets_export import _open_spreadsheet

logger = logging.getLogger(__name__)

DEFAULT_TAB = "Barcha o'quvchilar"

# Eksportdagi ustun joylashuvi (0-indeksli)
COL_KOD      = 0
COL_MAJBURIY = 5
COL_ASOSIY1  = 6
COL_ASOSIY2  = 7


def _parse_int_cell(value: str) -> Optional[int]:
    """Sheets katagidagi matnni butun songa aylantiradi. Bo'sh/noto'g'ri bo'lsa None."""
    value = (value or "").strip().replace(",", ".")
    if value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def preview_sheet_changes(tab_title: str = DEFAULT_TAB) -> dict:
    """
    Google Sheets bilan DB'ni solishtiradi, lekin HECH NARSANI o'zgartirmaydi.

    Qaytaradi:
        {
            "changes": [ {kod, ismlar, majburiy, asosiy1, asosiy2, eski_ball, yangi_ball}, ... ],
            "not_found": [kod, ...],      # Sheetsda bor, DB'da yo'q kodlar
            "invalid": [kod, ...],        # Ball katagi raqam emas
            "unchanged_count": int,
            "error": str | None,
        }
    """
    try:
        spreadsheet = _open_spreadsheet()
    except Exception as e:
        return {"error": f"Google Sheets'ga ulanib bo'lmadi: {e}"}

    try:
        ws = spreadsheet.worksheet(tab_title)
    except gspread.WorksheetNotFound:
        return {"error": f"'{tab_title}' varag'i topilmadi. Avval \"📗 Google Sheets Eksport\" orqali yuklang."}

    try:
        all_values = ws.get_all_values()
    except Exception as e:
        return {"error": f"Varaqni o'qib bo'lmadi: {e}"}

    # 1-qator: sarlavha, 2-qator: ustun nomlari, 3-qatordan — ma'lumot
    if len(all_values) < 3:
        return {"error": "Varaqda ma'lumot topilmadi."}

    data_rows = all_values[2:]

    changes: list[dict] = []
    not_found: list[str] = []
    invalid: list[str] = []
    unchanged_count = 0

    for row in data_rows:
        if not row or not row[COL_KOD].strip():
            continue  # bo'sh qator — eksport oxiridagi izoh qatorlari shu yerda tashlab ketiladi

        kod = row[COL_KOD].strip().upper()
        if kod.lower().startswith("hisobot") or kod.lower().startswith("jami"):
            continue  # footer/jami qatorlari

        talaba = talaba_topish(kod)
        if not talaba:
            not_found.append(kod)
            continue

        majburiy = _parse_int_cell(row[COL_MAJBURIY]) if len(row) > COL_MAJBURIY else None
        asosiy1  = _parse_int_cell(row[COL_ASOSIY1])  if len(row) > COL_ASOSIY1  else None
        asosiy2  = _parse_int_cell(row[COL_ASOSIY2])  if len(row) > COL_ASOSIY2  else None

        # Ball ustunlaridan biri bo'sh bo'lsa — bu qator tashlab ketiladi
        if majburiy is None and asosiy1 is None and asosiy2 is None:
            continue

        # Ammo agar to'liq emas (qisman to'ldirilgan) bo'lsa — xato sifatida belgilanadi
        if None in (majburiy, asosiy1, asosiy2):
            invalid.append(kod)
            continue

        oxirgi = talaba_songi_natija(kod)
        if (
            oxirgi
            and int(oxirgi["majburiy"]) == majburiy
            and int(oxirgi["asosiy_1"]) == asosiy1
            and int(oxirgi["asosiy_2"]) == asosiy2
        ):
            unchanged_count += 1
            continue

        changes.append({
            "kod": kod,
            "ismlar": talaba.get("ismlar", ""),
            "majburiy": majburiy,
            "asosiy1": asosiy1,
            "asosiy2": asosiy2,
            "eski_ball": oxirgi["umumiy_ball"] if oxirgi else None,
        })

    return {
        "changes": changes,
        "not_found": not_found,
        "invalid": invalid,
        "unchanged_count": unchanged_count,
        "error": None,
    }


def apply_sheet_changes(changes: list[dict]) -> int:
    """
    preview_sheet_changes() natijasidagi 'changes' ro'yxatini bazaga yozadi.
    Har bir o'zgarish test_natijalari jadvaliga yangi yozuv sifatida qo'shiladi
    (loyihadagi boshqa "natija tahrirlash" funksiyalari bilan bir xil uslubda —
    tarix saqlanib qoladi, eski natija o'chirilmaydi).

    Qaytaradi: muvaffaqiyatli yangilangan o'quvchilar soni.
    """
    updated = 0
    for c in changes:
        ok = natija_qosh(c["kod"], c["majburiy"], c["asosiy1"], c["asosiy2"])
        if ok:
            updated += 1
        else:
            logger.warning("sheets_import: %s uchun natija_qosh muvaffaqiyatsiz", c["kod"])
    return updated
