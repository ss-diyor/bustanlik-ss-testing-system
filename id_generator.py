"""
Shaxsiy ID raqam generatori moduli.

Sozlamalar (settings jadvalida saqlanadi):
  id_gen_prefix    — prefiks, masalan "SS"   (default: "SS")
  id_gen_digits    — raqam uzunligi          (default: "3"  → 001, 002 ...)
  id_gen_separator — prefiks va raqam orasidagi belgi (default: ""  → "SS001")
                     "-" qo'yilsa "SS-001" bo'ladi

Foydalanish:
  from id_generator import keyod_yarat, keyod_settings_ol, keyod_settings_saqla
"""

import re
from database import get_connection, release_connection, get_setting, set_setting


# ── Sozlamalarni o'qish / yozish ─────────────────────────────────────────────

def keyod_settings_ol() -> dict:
    return {
        "prefix":    get_setting("id_gen_prefix",    "SS"),
        "digits":    int(get_setting("id_gen_digits",    "3")),
        "separator": get_setting("id_gen_separator", ""),
    }


def keyod_settings_saqla(prefix: str = None, digits: int = None, separator: str = None):
    if prefix    is not None: set_setting("id_gen_prefix",    prefix.strip().upper())
    if digits    is not None: set_setting("id_gen_digits",    str(max(1, min(6, digits))))
    if separator is not None: set_setting("id_gen_separator", separator)


# ── Asosiy generator ─────────────────────────────────────────────────────────

def _keyod_qur(prefix: str, separator: str, digits: int, number: int) -> str:
    """Komponentlardan to'liq kod yig'adi: SS + "" + 001 → "SS001"."""
    return f"{prefix}{separator}{str(number).zfill(digits)}"


def _mavjud_max_raqam(prefix: str, separator: str) -> int:
    """
    Bazadagi barcha kodlar ichidan berilgan prefix bilan boshlanadigan
    eng katta raqamni qaytaradi. Topilmasa 0.
    """
    pattern = f"^{re.escape(prefix)}{re.escape(separator)}(\\d+)$"
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Barcha kodlarni olib, Python tomonida regex bilan filtrlaymiz
        cur.execute("SELECT kod FROM talabalar")
        rows = cur.fetchall()
        cur.close()
    finally:
        release_connection(conn)

    max_num = 0
    for (kod,) in rows:
        m = re.match(pattern, kod, re.IGNORECASE)
        if m:
            try:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    return max_num


def keyod_yarat(prefix: str = None, separator: str = None, digits: int = None) -> str:
    """
    Keyingi bo'sh kodni yaratadi.
    Agar parametrlar berilmasa, sozlamalardan oladi.
    """
    cfg = keyod_settings_ol()
    prefix    = (prefix    or cfg["prefix"]).strip().upper()
    separator = separator if separator is not None else cfg["separator"]
    digits    = digits    or cfg["digits"]

    max_num = _mavjud_max_raqam(prefix, separator)
    next_num = max_num + 1

    kod = _keyod_qur(prefix, separator, digits, next_num)

    # Namunaviy holda unikal ekanligini tekshirish (parallel insert bo'lmasa ham)
    from database import talaba_topish
    attempts = 0
    while talaba_topish(kod) is not None and attempts < 100:
        next_num += 1
        kod = _keyod_qur(prefix, separator, digits, next_num)
        attempts += 1

    return kod


def keyod_preview_list(prefix: str, separator: str, digits: int, count: int = 3) -> list[str]:
    """Ko'rsatish uchun namuna kodlar ro'yxatini qaytaradi."""
    max_num = _mavjud_max_raqam(prefix, separator)
    return [
        _keyod_qur(prefix, separator, digits, max_num + i)
        for i in range(1, count + 1)
    ]
