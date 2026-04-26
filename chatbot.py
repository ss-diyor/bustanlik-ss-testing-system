"""
Chatbot moduli — Gemini Flash-Lite asosida o'quvchi savol-javob tizimi.

Arxitektura:
  - O'quvchi "🤖 AI Chatbot" tugmasini bosadi
  - FSM orqali chat rejimiga kiradi
  - Har bir xabar Gemini API ga yuboriladi (suhbat tarixi saqlanadi)
  - "Chiqish" tugmasi bosiganda asosiy menyuga qaytadi
  - Admin panel orqali xususiyatni yoqish/o'chirish mumkin
  - Har bir suhbat chatbot_logs jadvaliga yoziladi
"""

import asyncio
import json
import logging
import urllib.request
from typing import Optional

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from database import (
    get_connection,
    release_connection,
    get_setting,
    chatbot_log_qosh,
)

import psycopg2.extras

logger = logging.getLogger(__name__)
router = Router()

CHATBOT_SETTING_KEY = "chatbot_enabled"
MAX_HISTORY = 10          # suhbatda saqlanadigan xabarlar soni (juft: user+assistant)
MAX_SAVOL_LEN = 1000      # o'quvchi savolining maksimal uzunligi

CHIQISH_MATNI = "🚪 Chatdan chiqish"

SYSTEM_PROMPT = (
    "Sen Bo'stonliq tuman ixtisoslashtirilgan maktabining test natijalari boti uchun yordamchi AI assistentsan. "
    "O'quvchilarga DTM tayyorgarlik, fanlarni o'zlashtirish jarayonida yordam berasan: "
    "fanlar bo'yicha savollar, o'qish maslahatlari, motivatsiya. "
    "Javoblarni qisqa, aniq va o'zbek tilida yoz. "
    "Faqat ta'lim mavzularida yordam ber, boshqa mavzularda muloyimlik bilan rad et."
)


# ─────────────────────────────────────────
# FSM holati
# ─────────────────────────────────────────

class ChatbotState(StatesGroup):
    chat_rejimi = State()


# ─────────────────────────────────────────
# Klaviatura
# ─────────────────────────────────────────

def chat_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CHIQISH_MATNI)]],
        resize_keyboard=True,
    )


# ─────────────────────────────────────────
# Gemini API chaqiruvi
# ─────────────────────────────────────────

def _call_gemini_sync(history: list[dict], yangi_savol: str) -> str:
    """Gemini Flash-Lite ga sinxron so'rov yuboradi (thread-safe)."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": yangi_savol})

    url = AI_BASE_URL.rstrip("/") + "/chat/completions"
    payload = {
        "model": AI_MODEL,
        "temperature": 0.5,
        "max_tokens": 800,
        "messages": messages,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        parsed = json.loads(resp.read().decode("utf-8"))
    return parsed["choices"][0]["message"]["content"].strip()


async def gemini_javob_ol(history: list[dict], savol: str) -> Optional[str]:
    """Async wrapper — threadpool orqali ishlaydi."""
    if not AI_API_KEY:
        return None
    try:
        return await asyncio.to_thread(_call_gemini_sync, history, savol)
    except Exception as e:
        logger.error(f"Gemini API xatosi: {e}")
        return None


# ─────────────────────────────────────────
# Talabani topish
# ─────────────────────────────────────────

def _talaba_ol(user_id: int) -> Optional[dict]:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT kod, ismlar FROM talabalar WHERE user_id = %s",
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return row


# ─────────────────────────────────────────
# Handlerlar
# ─────────────────────────────────────────

@router.message(F.text == "🤖 AI Chatbot")
async def chatbot_boshlash(message: Message, state: FSMContext):
    """O'quvchi chatbot tugmasini bosganida."""
    # Admin sozlamasini tekshir
    enabled = get_setting(CHATBOT_SETTING_KEY, "True")
    if enabled != "True":
        await message.answer(
            "⛔ <b>AI Chatbot hozirda o'chirilgan.</b>\n\n"
            "Admin tomonidan vaqtincha to'xtatilgan. Keyinroq urinib ko'ring.",
            parse_mode="HTML",
        )
        return

    # API kaliti borligini tekshir
    if not AI_API_KEY:
        await message.answer(
            "⚙️ <b>AI Chatbot sozlanmagan.</b>\n\n"
            "Iltimos, admindan <code>AI_API_KEY</code> ni sozlashni so'rang.",
            parse_mode="HTML",
        )
        return

    # Talabani topish (ixtiyoriy — log uchun)
    talaba = _talaba_ol(message.from_user.id)

    # FSM holatini o'rnatish va bo'sh tarix
    await state.set_state(ChatbotState.chat_rejimi)
    await state.update_data(history=[], talaba=talaba)

    ism = talaba["ismlar"] if talaba else "O'quvchi"
    await message.answer(
        f"🤖 <b>Salom, {ism}!</b>\n\n"
        "Men sizning AI yordamchingizman. DTM tayyorgarlik, fanlar bo'yicha "
        "savollar va o'qish maslahatlari uchun murojaat qiling.\n\n"
        "❓ Savolingizni yozing:\n"
        f"<i>(Chiqish uchun \"{CHIQISH_MATNI}\" tugmasini bosing)</i>",
        parse_mode="HTML",
        reply_markup=chat_keyboard(),
    )


@router.message(ChatbotState.chat_rejimi, F.text == CHIQISH_MATNI)
async def chatbot_chiqish(message: Message, state: FSMContext):
    """Chat rejimidan chiqish."""
    from keyboards import user_menu_keyboard
    from database import get_setting as gs

    ranking_enabled = gs("ranking_enabled", "True")
    stats_enabled = gs("stats_enabled", "True")

    await state.clear()
    await message.answer(
        "✅ Chatdan chiqdingiz. Asosiy menyuga qaytdingiz.",
        reply_markup=user_menu_keyboard(ranking_enabled, stats_enabled),
    )


@router.message(ChatbotState.chat_rejimi)
async def chatbot_savol_handler(message: Message, state: FSMContext):
    """O'quvchi savolini qabul qilib Gemini ga yuboradi."""
    savol = (message.text or "").strip()

    if not savol:
        await message.answer("📝 Iltimos, matn yozing.")
        return

    if len(savol) > MAX_SAVOL_LEN:
        await message.answer(
            f"⚠️ Savol juda uzun ({len(savol)} belgi). "
            f"Iltimos, {MAX_SAVOL_LEN} belgidan qisqaroq yozing."
        )
        return

    # Holatdan ma'lumotlar
    data = await state.get_data()
    history: list[dict] = data.get("history", [])
    talaba: Optional[dict] = data.get("talaba")

    # Kutish xabari
    wait_msg = await message.answer("⏳ Javob tayyorlanmoqda...")

    javob = await gemini_javob_ol(history, savol)

    await wait_msg.delete()

    if not javob:
        await message.answer(
            "❌ Javob olishda xatolik yuz berdi. Qayta urinib ko'ring.\n"
            "<i>Agar muammo davom etsa, adminga xabar bering.</i>",
            parse_mode="HTML",
        )
        return

    await message.answer(f"🤖 {javob}", parse_mode="HTML")

    # Tarixni yangilash (oxirgi MAX_HISTORY ta xabar)
    history.append({"role": "user", "content": savol})
    history.append({"role": "assistant", "content": javob})
    if len(history) > MAX_HISTORY * 2:
        history = history[-(MAX_HISTORY * 2):]
    await state.update_data(history=history)

    # Loglash
    try:
        chatbot_log_qosh(
            user_id=message.from_user.id,
            talaba_kod=talaba["kod"] if talaba else None,
            talaba_ism=talaba["ismlar"] if talaba else str(message.from_user.id),
            savol=savol,
            javob=javob,
        )
    except Exception as e:
        logger.error(f"Chatbot log yozishda xato: {e}")
