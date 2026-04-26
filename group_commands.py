"""
Guruh buyruqlari moduli.

Telegram guruhlarida ishlatiladigan buyruqlar:
    /top10  — Umumiy Top 10 reyting
    /top20  — Umumiy Top 20 reyting
    /top30  — Umumiy Top 30 reyting

Foydalanish:
    Bot guruhga qo'shilgandan so'ng, istalgan a'zo
    /top10, /top20 yoki /top30 deb yozsa — bot
    ro'yxatdan o'tgan o'quvchilarning reytingini
    shu guruhga chiqaradi.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from database import get_overall_ranking, get_setting

router = Router()
logger = logging.getLogger(__name__)

# Faqat guruh/superguruh xabarlarini qabul qiladi
router.message.filter(F.chat.type.in_({"group", "supergroup"}))


# ─── Yordamchi funksiyalar ────────────────────────────────────────────────────

def _medal(rank: int) -> str:
    """O'rin bo'yicha emoji qaytaradi."""
    if rank == 1:
        return "🥇"
    elif rank == 2:
        return "🥈"
    elif rank == 3:
        return "🥉"
    elif rank <= 10:
        return "🏅"
    else:
        return "▪️"


def _ball_emoji(ball: float) -> str:
    """Ball bo'yicha daraja emoji."""
    if ball >= 160:
        return "🔥"
    elif ball >= 130:
        return "⭐"
    elif ball >= 100:
        return "✅"
    else:
        return "📝"


def _reyting_matni_yasash(talabalar: list, limit: int) -> str:
    """
    Top-N reyting uchun chiroyli matn yasaydi.

    Namuna:
        🏆 TOP-10 REYTING
        ━━━━━━━━━━━━━━━━━━━
        🥇 1. Ali Valiyev (10-A) — 🔥 182.3 ball
        🥈 2. Zulfiya Rahimova (11-B) — ⭐ 171.0 ball
        ...
    """
    if not talabalar:
        return (
            "📭 <b>Hozircha ma'lumotlar mavjud emas.</b>\n\n"
            "O'quvchilar test natijalarini topshirganidan so'ng reyting ko'rsatiladi."
        )

    # Limit bo'yicha qisqartirish
    talabalar = talabalar[:limit]

    matn = f"🏆 <b>TOP-{limit} REYTING</b>\n"
    matn += "━━━━━━━━━━━━━━━━━━━\n\n"

    for i, t in enumerate(talabalar, 1):
        ism = t.get("ismlar", "Noma'lum")
        sinf = t.get("sinf") or "—"
        ball = float(t.get("umumiy_ball", 0))
        medal = _medal(i)
        ball_em = _ball_emoji(ball)

        matn += f"{medal} <b>{i}.</b> {ism}"
        if sinf and sinf != "—":
            matn += f" <i>({sinf})</i>"
        matn += f" — {ball_em} <b>{ball:.1f}</b> ball\n"

    matn += f"\n━━━━━━━━━━━━━━━━━━━\n"
    matn += f"📊 Jami ko'rsatildi: <b>{len(talabalar)} ta</b> o'quvchi\n"
    matn += f"📌 <i>Oxirgi test natijasi asosida</i>"

    return matn


async def _top_handler(message: Message, limit: int):
    """
    Umumiy Top-N reyting handlerining asosiy logikasi.
    Limit 10, 20 yoki 30 bo'lishi mumkin.
    """
    # Reyting yoqilganligini tekshirish
    ranking_enabled = get_setting("ranking_enabled", "True")
    if ranking_enabled.lower() != "true":
        await message.answer(
            "⛔ <b>Reyting tizimi hozircha o'chirilgan.</b>\n"
            "Admin tomonidan yoqilganidan so'ng foydalanish mumkin.",
            parse_mode="HTML",
        )
        return

    try:
        # Barcha o'quvchilarni ball bo'yicha olish (top-50 qaytaradi)
        talabalar = get_overall_ranking()
        matn = _reyting_matni_yasash(talabalar, limit)
        await message.answer(matn, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Top-{limit} reyting chiqarishda xato: {e}")
        await message.answer(
            "⚠️ <b>Ma'lumotlarni olishda xato yuz berdi.</b>\n"
            "Iltimos, keyinroq urinib ko'ring.",
            parse_mode="HTML",
        )


# ─── /top10 ───────────────────────────────────────────────────────────────────

@router.message(Command("top10"))
async def top10_handler(message: Message):
    """/top10 — Top 10 o'quvchini guruhda ko'rsatadi."""
    await _top_handler(message, limit=10)


# ─── /top20 ───────────────────────────────────────────────────────────────────

@router.message(Command("top20"))
async def top20_handler(message: Message):
    """/top20 — Top 20 o'quvchini guruhda ko'rsatadi."""
    await _top_handler(message, limit=20)


# ─── /top30 ───────────────────────────────────────────────────────────────────

@router.message(Command("top30"))
async def top30_handler(message: Message):
    """/top30 — Top 30 o'quvchini guruhda ko'rsatadi."""
    await _top_handler(message, limit=30)


# ─── /top (umumiy, limitni o'zi kiritadi) ────────────────────────────────────

@router.message(Command("top"))
async def top_handler(message: Message):
    """
    /top N — N ta o'quvchini ko'rsatadi.
    N 1 dan 50 gacha bo'lishi mumkin.
    Agar N ko'rsatilmasa, default 10 ta ko'rsatadi.

    Misol: /top 15
    """
    # Buyruqdan sonni ajratib olish: "/top 15" → 15
    args = message.text.strip().split()
    limit = 10  # default

    if len(args) >= 2:
        try:
            limit = int(args[1])
            if limit < 1:
                limit = 1
            elif limit > 50:
                await message.answer(
                    "⚠️ Maksimal limit <b>50</b> ta.\n"
                    "Masalan: <code>/top 50</code>",
                    parse_mode="HTML",
                )
                return
        except ValueError:
            await message.answer(
                "❌ Noto'g'ri son.\n"
                "Masalan: <code>/top 15</code>",
                parse_mode="HTML",
            )
            return

    await _top_handler(message, limit=limit)
