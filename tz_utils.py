"""
Loyiha bo'ylab yagona timezone yordamchi moduli.
Barcha datetime.now() chaqiruvlari shu moduldan o'tishi kerak.
"""
from zoneinfo import ZoneInfo
from datetime import datetime

TZ = ZoneInfo("Asia/Tashkent")   # UTC+5


def now() -> datetime:
    """Toshkent vaqtida hozirgi datetime qaytaradi."""
    return datetime.now(TZ)


def now_str(fmt: str = "%d.%m.%Y %H:%M") -> str:
    """Toshkent vaqtida formatlangan satr qaytaradi."""
    return now().strftime(fmt)
