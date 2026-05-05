"""
Bot holati monitoringi moduli.
/status buyrug'i uchun barcha ma'lumotlarni yig'adi.
"""

import os
import time
import asyncio
import logging
from datetime import datetime, timezone

import psutil

logger = logging.getLogger(__name__)

# Bot ishga tushgan vaqt — bot.py da BOT_START_TIME = time.time() qo'shiladi
_start_time: float = time.time()


def set_start_time(t: float):
    """bot.py dan chaqiriladi — aniq ishga tushish vaqtini o'rnatadi."""
    global _start_time
    _start_time = t


def _uptime_str() -> str:
    elapsed = int(time.time() - _start_time)
    d, r  = divmod(elapsed, 86400)
    h, r  = divmod(r, 3600)
    m, s  = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d} kun")
    if h: parts.append(f"{h} soat")
    if m: parts.append(f"{m} daqiqa")
    parts.append(f"{s} soniya")
    return " ".join(parts)


def _memory_info() -> dict:
    proc = psutil.Process(os.getpid())
    mem  = proc.memory_info()
    vm   = psutil.virtual_memory()
    return {
        "bot_rss_mb":  round(mem.rss  / 1024 / 1024, 1),
        "bot_vms_mb":  round(mem.vms  / 1024 / 1024, 1),
        "sys_total_gb": round(vm.total / 1024 / 1024 / 1024, 1),
        "sys_used_pct": vm.percent,
        "sys_avail_mb": round(vm.available / 1024 / 1024, 1),
    }


def _cpu_info() -> dict:
    proc = psutil.Process(os.getpid())
    return {
        "bot_cpu_pct": round(proc.cpu_percent(interval=0.2), 1),
        "sys_cpu_pct": round(psutil.cpu_percent(interval=0.2), 1),
        "cpu_count":   psutil.cpu_count(),
    }


def _disk_info() -> dict:
    disk = psutil.disk_usage("/")
    return {
        "total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
        "used_gb":  round(disk.used  / 1024 / 1024 / 1024, 1),
        "free_gb":  round(disk.free  / 1024 / 1024 / 1024, 1),
        "used_pct": disk.percent,
    }


def _db_ping() -> tuple[bool, float]:
    """DB ga ulanib SELECT 1 yuboradi. (ok, ms) qaytaradi."""
    try:
        from database import get_connection, release_connection
        t0   = time.perf_counter()
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        release_connection(conn)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return True, ms
    except Exception as e:
        logger.warning("DB ping xatosi: %s", e)
        return False, 0.0


def _db_stats() -> dict:
    """Asosiy jadval statistikasini qaytaradi."""
    try:
        from database import get_connection, release_connection
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM talabalar")
        talabalar = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM test_natijalari")
        natijalar = cur.fetchone()[0]
        cur.execute(
            "SELECT COUNT(*) FROM test_natijalari WHERE test_sanasi >= NOW() - INTERVAL '24 hours'"
        )
        bugun = cur.fetchone()[0]
        cur.close()
        release_connection(conn)
        return {"talabalar": talabalar, "natijalar": natijalar, "bugun": bugun}
    except Exception as e:
        logger.warning("DB stats xatosi: %s", e)
        return {"talabalar": "?", "natijalar": "?", "bugun": "?"}


def _bar(pct: float, width: int = 10) -> str:
    """Oddiy matnli progress bar."""
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _status_icon(ok: bool) -> str:
    return "🟢" if ok else "🔴"


async def build_status_text() -> str:
    """To'liq /status xabarini yaratadi."""
    loop = asyncio.get_event_loop()

    # CPU va disk blokirovka qiluvchi — thread pool da yuramiz
    cpu   = await loop.run_in_executor(None, _cpu_info)
    mem   = _memory_info()
    disk  = _disk_info()
    db_ok, db_ms = await loop.run_in_executor(None, _db_ping)
    stats = await loop.run_in_executor(None, _db_stats)
    now   = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S UTC")

    mem_icon  = _status_icon(mem["sys_used_pct"] < 85)
    cpu_icon  = _status_icon(cpu["sys_cpu_pct"] < 80)
    disk_icon = _status_icon(disk["used_pct"] < 90)
    db_icon   = _status_icon(db_ok)

    text = (
        f"<b>📡 Bot holati</b>\n"
        f"<code>{now}</code>\n"
        f"⏱ Ishlash vaqti: <b>{_uptime_str()}</b>\n\n"

        f"<b>🗄 Ma'lumotlar bazasi</b>\n"
        f"{db_icon} Ulanish: <b>{'OK' if db_ok else 'XATO'}</b>"
        + (f"  <code>{db_ms} ms</code>" if db_ok else "") + "\n"
        f"👥 O'quvchilar: <b>{stats['talabalar']}</b>\n"
        f"📝 Natijalar: <b>{stats['natijalar']}</b>\n"
        f"🕐 So'nggi 24 soat: <b>{stats['bugun']}</b> yangi natija\n\n"

        f"<b>💾 Xotira</b>\n"
        f"{mem_icon} Bot: <b>{mem['bot_rss_mb']} MB</b>\n"
        f"Tizim: {_bar(mem['sys_used_pct'])} "
        f"<b>{mem['sys_used_pct']}%</b> "
        f"(bo'sh: {mem['sys_avail_mb']} MB)\n\n"

        f"<b>⚙️ Protsessor</b>\n"
        f"{cpu_icon} Bot CPU: <b>{cpu['bot_cpu_pct']}%</b>\n"
        f"Tizim CPU: {_bar(cpu['sys_cpu_pct'])} "
        f"<b>{cpu['sys_cpu_pct']}%</b> "
        f"({cpu['cpu_count']} yadrо)\n\n"

        f"<b>💿 Disk</b>\n"
        f"{disk_icon} {_bar(disk['used_pct'])} "
        f"<b>{disk['used_pct']}%</b>\n"
        f"Ishlatilgan: {disk['used_gb']} GB / {disk['total_gb']} GB "
        f"(bo'sh: {disk['free_gb']} GB)\n"
    )
    return text
