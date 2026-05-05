"""
Rate Limiter & Spam Himoyasi — Aiogram 3 Middleware

Qoidalar:
  • Oddiy foydalanuvchi:  oyna ichida MAX_REQUESTS ta so'rovdan ko'p yuborse → ogohlantiriladi
  • Ogohlantirish soni WARN_BEFORE_BAN ga yetsa → vaqtincha ban (BAN_DURATION soniya)
  • Ban paytida kelgan har so'rov log qilinadi, javob berilmaydi
  • Admin va adminlar soni cheksiz — ular hech qachon bloklanshmaydi
  • Har bir bloklangan foydalanuvchi haqida super-adminga Telegram xabar ketadi

Sozlamalar (environment yoki to'g'ridan config.py orqali):
  RATE_LIMIT_REQUESTS   — oyna ichida nechta so'rov (default: 15)
  RATE_LIMIT_WINDOW     — oyna uzunligi soniyada (default: 60)
  RATE_LIMIT_BAN        — ban davomiyligi soniyada (default: 300 = 5 daqiqa)
  RATE_LIMIT_WARN       — necha marta ogohlantirilgandan keyin ban (default: 3)
"""

import os
import time
import logging
from collections import defaultdict, deque
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update

logger = logging.getLogger(__name__)

# ── Sozlamalar ──────────────────────────────────────────────────────────────
MAX_REQUESTS  = int(os.getenv("RATE_LIMIT_REQUESTS", 15))   # oyna ichida max so'rov
WINDOW_SEC    = int(os.getenv("RATE_LIMIT_WINDOW",   60))   # oyna uzunligi (soniya)
BAN_DURATION  = int(os.getenv("RATE_LIMIT_BAN",     300))   # ban davomiyligi (soniya)
WARN_BEFORE_BAN = int(os.getenv("RATE_LIMIT_WARN",    3))   # ogohlantirish soni → ban


class _UserState:
    """Bitta foydalanuvchining rate limit holati."""
    __slots__ = ("requests", "warnings", "banned_until", "total_blocked")

    def __init__(self):
        self.requests: deque[float] = deque()   # so'rov vaqtlari (float timestamp)
        self.warnings: int = 0
        self.banned_until: float = 0.0
        self.total_blocked: int = 0


class RateLimitMiddleware(BaseMiddleware):
    """
    Barcha kiruvchi update larni tekshiradi.
    dp.update.middleware(RateLimitMiddleware()) bilan ulanadi.
    """

    def __init__(self):
        self._states: defaultdict[int, _UserState] = defaultdict(_UserState)
        # Admin ID lari — ular hech qachon bloklanmaydi
        try:
            from config import ADMIN_IDS
            self._admin_ids: frozenset[int] = frozenset(ADMIN_IDS)
        except Exception:
            self._admin_ids = frozenset()

    # ── Asosiy kirish nuqtasi ──────────────────────────────────────────────
    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        user_id = self._extract_user_id(event)
        if user_id is None or user_id in self._admin_ids:
            return await handler(event, data)

        now = time.monotonic()
        state = self._states[user_id]

        # ── Ban tekshiruvi ──────────────────────────────────────────────────
        if state.banned_until > now:
            state.total_blocked += 1
            remaining = int(state.banned_until - now)
            logger.warning(
                "Bloklangan foydalanuvchi %s — so'rov rad etildi (%d soniya qoldi, jami %d blok)",
                user_id, remaining, state.total_blocked,
            )
            # Har 10 ta bloklangan so'rovda eslatma yuboramiz
            if state.total_blocked % 10 == 1:
                await self._send_to_user(
                    event,
                    f"🚫 Siz vaqtincha bloklangansiz.\n"
                    f"⏱ {remaining // 60} daqiqa {remaining % 60} soniyadan so'ng qayta urinib ko'ring.",
                )
            return  # handleerni chaqirmaymiz

        # ── Oyna tozalash va hisoblash ─────────────────────────────────────
        cutoff = now - WINDOW_SEC
        while state.requests and state.requests[0] < cutoff:
            state.requests.popleft()

        state.requests.append(now)

        if len(state.requests) <= MAX_REQUESTS:
            # Normal holat — handlerga o'tamiz
            return await handler(event, data)

        # ── Limit oshdi ────────────────────────────────────────────────────
        state.warnings += 1
        logger.warning(
            "Rate limit: user %s — %d/%d so'rov, ogohlantirish %d/%d",
            user_id, len(state.requests), MAX_REQUESTS,
            state.warnings, WARN_BEFORE_BAN,
        )

        if state.warnings >= WARN_BEFORE_BAN:
            # Ban berish
            state.banned_until = now + BAN_DURATION
            state.warnings = 0
            state.requests.clear()
            state.total_blocked = 0
            mins = BAN_DURATION // 60
            logger.warning("BAN: user %s — %d daqiqa bloklandi", user_id, mins)
            await self._notify_admins(event, user_id, mins)
            await self._send_to_user(
                event,
                f"⛔ <b>Siz {mins} daqiqaga bloklangansiz.</b>\n\n"
                f"Juda ko'p so'rov yuborgansiz. "
                f"Iltimos, keyinchalik qayta urinib ko'ring.",
            )
        else:
            remaining_warns = WARN_BEFORE_BAN - state.warnings
            await self._send_to_user(
                event,
                f"⚠️ <b>Ogohlantirish {state.warnings}/{WARN_BEFORE_BAN}</b>\n\n"
                f"So'rovlar juda tez yuborilmoqda. "
                f"Sekinroq yuboring.\n"
                f"Yana {remaining_warns} marta takrorlansa, vaqtincha bloklasiz.",
            )
        return  # handleerni chaqirmaymiz

    # ── Yordamchi metodlar ─────────────────────────────────────────────────

    @staticmethod
    def _extract_user_id(event: Update) -> int | None:
        if event.message:
            return event.message.from_user.id if event.message.from_user else None
        if event.callback_query:
            return event.callback_query.from_user.id
        if event.inline_query:
            return event.inline_query.from_user.id
        return None

    @staticmethod
    async def _send_to_user(event: Update, text: str):
        """Foydalanuvchiga xabar yuboradi (xatolarni yutadi)."""
        try:
            if event.message:
                await event.message.answer(text, parse_mode="HTML")
            elif event.callback_query:
                await event.callback_query.answer(
                    text.replace("<b>", "").replace("</b>", "")[:200],
                    show_alert=True,
                )
        except Exception as exc:
            logger.debug("Rate limiter: foydalanuvchiga xabar yuborib bo'lmadi: %s", exc)

    async def _notify_admins(self, event: Update, user_id: int, mins: int):
        """Ban haqida super-adminga xabar yuboradi."""
        try:
            bot = None
            if event.message:
                bot = event.message.bot
                user = event.message.from_user
            elif event.callback_query:
                bot = event.callback_query.message.bot
                user = event.callback_query.from_user
            else:
                return

            if bot is None:
                return

            username = f"@{user.username}" if user.username else f"ID: {user_id}"
            full_name = user.full_name or "Noma'lum"
            text = (
                f"🚨 <b>Spam himoyasi: Ban berildi</b>\n\n"
                f"👤 Foydalanuvchi: <b>{full_name}</b> ({username})\n"
                f"🆔 ID: <code>{user_id}</code>\n"
                f"⏱ Ban davomiyligi: <b>{mins} daqiqa</b>\n"
                f"📊 {WINDOW_SEC} soniyada {MAX_REQUESTS}+ so'rov yubordi"
            )
            for admin_id in self._admin_ids:
                try:
                    await bot.send_message(admin_id, text, parse_mode="HTML")
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("Admin notification xatosi: %s", exc)

    # ── Admin buyruqlari (/rl_status, /rl_unban) ───────────────────────────

    def get_stats(self) -> str:
        """Barcha foydalanuvchilar rate limit statistikasini qaytaradi."""
        now = time.monotonic()
        banned = [
            (uid, int(st.banned_until - now))
            for uid, st in self._states.items()
            if st.banned_until > now
        ]
        total_users = len(self._states)
        text = (
            f"📊 <b>Rate Limiter statistikasi</b>\n\n"
            f"Kuzatilayotgan foydalanuvchilar: <b>{total_users}</b>\n"
            f"Hozir bloklangan: <b>{len(banned)}</b>\n\n"
        )
        if banned:
            text += "<b>Bloklangan foydalanuvchilar:</b>\n"
            for uid, secs in sorted(banned, key=lambda x: -x[1])[:10]:
                text += f"• <code>{uid}</code> — {secs // 60}m {secs % 60}s qoldi\n"
        return text

    def unban(self, user_id: int) -> bool:
        """Foydalanuvchini qo'lda banidan chiqaradi."""
        if user_id in self._states:
            st = self._states[user_id]
            if st.banned_until > time.monotonic():
                st.banned_until = 0.0
                st.warnings = 0
                st.requests.clear()
                st.total_blocked = 0
                return True
        return False

    def reset(self, user_id: int):
        """Foydalanuvchi holatini to'liq tozalaydi."""
        if user_id in self._states:
            del self._states[user_id]


# Global instance — bot.py va admin.py dan import qilinadi
rate_limiter = RateLimitMiddleware()
