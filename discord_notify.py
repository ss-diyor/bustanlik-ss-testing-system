# discord_notify.py
# Discord Webhook integratsiya moduli
# Bo'stonliq tuman ixtisoslashtirilgan maktabi - DTM Testing System

import aiohttp
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Webhook URL larni environment'dan olish
# ──────────────────────────────────────────────
# .env yoki Railway Variables ga qo'shing:
#   DISCORD_WEBHOOK_MAIN   → Asosiy kanal (barcha xabarlar)
#   DISCORD_WEBHOOK_ADMIN  → Faqat admin bildirishnomalari (ixtiyoriy)
#   DISCORD_WEBHOOK_RANK   → Reyting kanali (ixtiyoriy)

WEBHOOK_MAIN  = os.getenv("DISCORD_WEBHOOK_MAIN", "")
WEBHOOK_ADMIN = os.getenv("DISCORD_WEBHOOK_ADMIN", "") or WEBHOOK_MAIN
WEBHOOK_RANK  = os.getenv("DISCORD_WEBHOOK_RANK",  "") or WEBHOOK_MAIN

# ──────────────────────────────────────────────
# Ranglar (Discord embed color kodlari)
# ──────────────────────────────────────────────
COLOR_GREEN  = 0x2ecc71   # Yangi natija / muvaffaqiyat
COLOR_BLUE   = 0x3498db   # Umumiy xabar
COLOR_GOLD   = 0xf39c12   # Reyting
COLOR_PURPLE = 0x9b59b6   # Backup
COLOR_RED    = 0xe74c3c   # Xato / ogohlantirish
COLOR_TEAL   = 0x1abc9c   # Yangi o'quvchi
COLOR_GRAY   = 0x95a5a6   # Bot holati


# ──────────────────────────────────────────────
# Asosiy yuborish funksiyasi
# ──────────────────────────────────────────────
async def send_discord(
    title: str,
    description: str,
    color: int = COLOR_BLUE,
    fields: list = None,
    footer: str = "Bo'stonliq SS Testing System",
    webhook_url: str = None,
):
    """
    Discord kanaliga Embed xabar yuboradi.

    Parametrlar:
        title       — Embed sarlavhasi
        description — Asosiy matn (markdown qo'llab-quvvatlanadi)
        color       — Embed yon chizig'i rangi (hex int)
        fields      — [{"name": "...", "value": "...", "inline": True/False}]
        footer      — Pastki matn
        webhook_url — Qaysi webhook'ga yuborish (bo'sh bo'lsa WEBHOOK_MAIN)
    """
    url = webhook_url or WEBHOOK_MAIN
    if not url:
        logger.warning("Discord webhook URL topilmadi. DISCORD_WEBHOOK_MAIN ni .env ga qo'shing.")
        return

    embed = {
        "title": title,
        "description": description,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": footer},
        "fields": fields or [],
    }
    payload = {
        "username": "SS Testing Bot",
        "avatar_url": "https://i.imgur.com/4M34hi2.png",  # ixtiyoriy avatar
        "embeds": [embed],
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 204:
                    logger.debug(f"Discord xabari yuborildi: {title}")
                elif resp.status == 429:
                    logger.warning("Discord rate limit. Biroz kuting.")
                else:
                    body = await resp.text()
                    logger.warning(f"Discord webhook xato {resp.status}: {body[:200]}")
    except aiohttp.ClientError as e:
        logger.error(f"Discord aiohttp xatosi: {e}")
    except Exception as e:
        logger.error(f"Discord yuborishda kutilmagan xato: {e}")


# ──────────────────────────────────────────────
# Maxsus bildirishnoma funksiyalari
# ──────────────────────────────────────────────

async def notify_new_result(
    student_name: str,
    kod: str,
    sinf: str,
    yonalish: str,
    majburiy: int,
    asosiy_1: int,
    asosiy_2: int,
    umumiy_ball: float,
    class_rank: int = None,
    overall_rank: int = None,
    diff: float = None,
):
    """
    Yangi natija kiritilganda Discord kanaliga bildirishnoma yuboradi.
    admin.py → bildirishnoma_yuborish() ichidan chaqiriladi.
    """
    foiz = round((umumiy_ball / 189) * 100, 1)

    rank_text = ""
    if class_rank:
        rank_text += f"📍 Sinfda: **{class_rank}-o'rin**\n"
    if overall_rank:
        rank_text += f"🌐 Umumiy: **{overall_rank}-o'rin**\n"

    diff_text = ""
    if diff is not None:
        if diff > 0:
            diff_text = f"📈 O'zgarish: **+{diff} ball** ⬆️"
        elif diff < 0:
            diff_text = f"📉 O'zgarish: **{diff} ball** ⬇️"
        else:
            diff_text = "⏺ O'zgarish yo'q"

    description = (
        f"👤 **{student_name}** (`{kod}`)\n"
        f"🏫 {sinf} sinf · 🎯 {yonalish}\n\n"
        f"{rank_text}{diff_text}"
    )

    fields = [
        {"name": "📘 Majburiy",  "value": f"{majburiy}/30 → **{majburiy * 1.1:.1f}**",  "inline": True},
        {"name": "📗 1-asosiy",  "value": f"{asosiy_1}/30 → **{asosiy_1 * 3.1:.1f}**", "inline": True},
        {"name": "📙 2-asosiy",  "value": f"{asosiy_2}/30 → **{asosiy_2 * 2.1:.1f}**", "inline": True},
        {"name": "🏆 Umumiy ball", "value": f"**{umumiy_ball} / 189**",                  "inline": True},
        {"name": "📊 Foiz",       "value": f"**{foiz}%**",                                "inline": True},
    ]

    await send_discord(
        title="📥 Yangi Natija Kiritildi",
        description=description,
        color=COLOR_GREEN,
        fields=fields,
        webhook_url=WEBHOOK_ADMIN,
    )


async def notify_daily_ranking(ranking_text: str, total_students: int = 0):
    """
    Kundalik Top-10 reytingni Discord kanaliga yuboradi.
    bot.py → group_ranking_scheduler() ichidan chaqiriladi.
    """
    footer_text = f"Bo'stonliq SS · Jami o'quvchilar: {total_students}" if total_students else "Bo'stonliq SS Testing System"

    await send_discord(
        title="🏆 Kundalik Reyting — Top 10",
        description=ranking_text[:4000],  # Discord limit
        color=COLOR_GOLD,
        footer=footer_text,
        webhook_url=WEBHOOK_RANK,
    )


async def notify_backup_sent(student_count: int, filename: str = ""):
    """
    Kundalik backup yuborilganda Discord kanaliga xabar yuboradi.
    bot.py → send_backup() ichidan chaqiriladi.
    """
    fields = [
        {"name": "📁 Fayl",          "value": filename or "backup.xlsx", "inline": True},
        {"name": "👥 O'quvchilar",   "value": str(student_count),         "inline": True},
        {"name": "🕐 Vaqt",          "value": datetime.now().strftime("%d.%m.%Y %H:%M"), "inline": True},
    ]
    await send_discord(
        title="💾 Kundalik Backup Muvaffaqiyatli Yuborildi",
        description="Ma'lumotlar bazasi zaxira nusxasi adminlarga yuborildi.",
        color=COLOR_PURPLE,
        fields=fields,
        webhook_url=WEBHOOK_ADMIN,
    )


async def notify_new_student(
    student_name: str,
    kod: str,
    sinf: str,
    yonalish: str,
    maktab: str = "",
):
    """
    Yangi o'quvchi qo'shilganda Discord kanaliga xabar yuboradi.
    admin.py → guruhlarga_yangi_oquvchi_yuborish() ichidan chaqiriladi.
    """
    description = (
        f"👤 **{student_name}** (`{kod}`)\n"
        f"🏫 {sinf} sinf · 🎯 {yonalish}"
    )
    if maktab:
        description += f"\n🏛 {maktab}"

    await send_discord(
        title="🆕 Yangi O'quvchi Qo'shildi",
        description=description,
        color=COLOR_TEAL,
        webhook_url=WEBHOOK_ADMIN,
    )


async def notify_bot_started():
    """
    Bot ishga tushganda Discord kanaliga xabar yuboradi.
    bot.py → main() ichidan chaqiriladi.
    """
    await send_discord(
        title="🚀 Bot Ishga Tushdi",
        description=(
            f"**bustanlik-ss-testing-system** muvaffaqiyatli ishga tushdi.\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        ),
        color=COLOR_BLUE,
        webhook_url=WEBHOOK_ADMIN,
    )


async def notify_error(context: str, error: str):
    """
    Kritik xato yuz berganda Discord kanaliga ogohlantirish yuboradi.
    """
    await send_discord(
        title="⚠️ Xato Yuz Berdi",
        description=f"**Kontekst:** {context}\n```\n{str(error)[:500]}\n```",
        color=COLOR_RED,
        webhook_url=WEBHOOK_ADMIN,
    )


async def notify_class_stats(
    maktab_nomi: str,
    jami: int,
    ortacha: float,
    eng_yuqori: float,
    eng_past: float,
    sinf_breakdown: list = None,
):
    """
    Statistika ko'rilganda Discord kanaliga yuboradi.
    admin.py → stats_maktab_callback() ichidan chaqiriladi.

    sinf_breakdown — ixtiyoriy, har bir sinf bo'yicha:
        [{"sinf": "11A", "soni": 12, "ortacha": 145.3}, ...]
    """
    fields = [
        {"name": "👥 Jami o'quvchilar", "value": f"**{jami} ta**",          "inline": True},
        {"name": "📈 O'rtacha ball",     "value": f"**{ortacha}**",           "inline": True},
        {"name": "🏆 Eng yuqori",        "value": f"**{eng_yuqori} ball**",   "inline": True},
        {"name": "📉 Eng past",          "value": f"**{eng_past} ball**",     "inline": True},
    ]

    if sinf_breakdown:
        breakdown_text = "\n".join(
            f"`{s['sinf']}` — {s['soni']} ta · o'rtacha **{s['ortacha']}**"
            for s in sinf_breakdown[:10]  # max 10 sinf
        )
        fields.append({
            "name": "🏫 Sinflar bo'yicha",
            "value": breakdown_text,
            "inline": False,
        })

    await send_discord(
        title=f"📊 Statistika — {maktab_nomi}",
        description=f"**{maktab_nomi}** maktabi bo'yicha joriy statistika.",
        color=COLOR_BLUE,
        fields=fields,
        webhook_url=WEBHOOK_ADMIN,
    )


async def notify_appeal_received(student_name: str, kod: str, message_preview: str):
    """
    Yangi murojaat (appeal) kelganda Discord kanaliga xabar yuboradi.
    """
    await send_discord(
        title="📩 Yangi Murojaat Keldi",
        description=(
            f"👤 **{student_name}** (`{kod}`) dan murojaat:\n\n"
            f"> {message_preview[:300]}"
        ),
        color=COLOR_BLUE,
        webhook_url=WEBHOOK_ADMIN,
    )
