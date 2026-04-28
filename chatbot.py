"""
Chatbot moduli — Groq LLM asosida o'quvchi savol-javob tizimi.
"""

import asyncio
import json
import logging
import urllib.request
import urllib.error
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
MAX_HISTORY = 10
MAX_SAVOL_LEN = 1000

CHIQISH_MATNI = "🚪 Chatdan chiqish"

SYSTEM_PROMPT = (
    "Sen Bo'stonliq tuman ixtisoslashtirilgan maktabining test natijalari boti uchun AI yordamchisan. "
    "O'quvchilarga DTM imtihonlariga tayyorgarlik, fanlarni o'zlashtirish jarayonida yordam berasan: "
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
# Groq API chaqiruvi
# ─────────────────────────────────────────

def _build_messages(history: list[dict], yangi_savol: str) -> list[dict]:
    messages = []
    if history:
        messages.extend(history)
        messages.append({"role": "user", "content": yangi_savol})
    else:
        birinchi_savol = (
            f"[Tizim ko'rsatmasi: {SYSTEM_PROMPT}]\n\n"
            f"Savol: {yangi_savol}"
        )
        messages.append({"role": "user", "content": birinchi_savol})
    return messages


def _call_gemini_sync(history: list[dict], yangi_savol: str) -> str:
    messages = _build_messages(history, yangi_savol)

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
            "User-Agent": "Mozilla/5.0",  # Cloudflare 403 blokini oldini olish
        },
    )

    logger.debug(f"Groq API ga so'rov: url={url}, model={AI_MODEL}")

    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8")

        logger.debug(f"Groq API javobi: {body[:300]}")
        parsed = json.loads(body)

    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8")
        except Exception:
            pass
        logger.error(
            f"Groq API HTTP xatosi: status={e.code}, reason={e.reason}, "
            f"body={error_body[:500]}"
        )
        raise

    except urllib.error.URLError as e:
        logger.error(f"Groq API tarmoq xatosi: {e.reason}")
        raise

    except json.JSONDecodeError as e:
        logger.error(f"Groq API javobini parse qilishda xato: {e}")
        raise

    if "choices" not in parsed or not parsed["choices"]:
        logger.error(f"Groq API kutilmagan javob strukturasi: {parsed}")
        raise ValueError(f"API javobida 'choices' yo'q: {parsed}")

    content = parsed["choices"][0].get("message", {}).get("content", "")
    if not content:
        logger.error(f"Groq API bo'sh content qaytardi: {parsed}")
        raise ValueError("API bo'sh javob qaytardi")

    return content.strip()


async def gemini_javob_ol(history: list[dict], savol: str) -> Optional[str]:
    if not AI_API_KEY:
        logger.error("❌ AI_API_KEY bo'sh! Railway Variables ni tekshiring.")
        return None
    try:
        result = await asyncio.to_thread(_call_gemini_sync, history, savol)
        logger.info(f"✅ Groq javob berdi: {result[:50]}")
        return result
    except Exception as e:
        logger.error(f"❌ Groq xatosi: {type(e).__name__}: {e}")
        return None


# ─────────────────────────────────────────
# Talabani topish
# ─────────────────────────────────────────

def _talaba_ol(user_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT kod, ismlar FROM talabalar WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
        cur.close()
        return row
    except Exception as e:
        logger.error(f"Talabani olishda xato: {e}")
        return None
    finally:
        release_connection(conn)


# ─────────────────────────────────────────
# Handlerlar
# ─────────────────────────────────────────

@router.message(F.text == "🤖 AI Chatbot")
async def chatbot_boshlash(message: Message, state: FSMContext):
    enabled = get_setting(CHATBOT_SETTING_KEY, "True")
    if enabled != "True":
        await message.answer(
            "⛔ <b>AI Chatbot hozirda o'chirilgan.</b>\n\n"
            "Admin tomonidan vaqtincha to'xtatilgan. Keyinroq urinib ko'ring.",
            parse_mode="HTML",
        )
        return

    if not AI_API_KEY:
        await message.answer(
            "⚙️ <b>AI Chatbot sozlanmagan.</b>\n\n"
            "Iltimos, admindan <code>AI_API_KEY</code> ni sozlashni so'rang.",
            parse_mode="HTML",
        )
        return

    talaba = _talaba_ol(message.from_user.id)
    await state.set_state(ChatbotState.chat_rejimi)
    await state.update_data(history=[], talaba=talaba)

    ism = talaba["ismlar"] if talaba else "O'quvchi"
    await message.answer(
        f"🤖 <b>Assalomu alaykum, {ism}!</b>\n\n"
        "Men sizning AI yordamchingizman. Imtihonlarga tayyorgarlik, fanlar bo'yicha "
        "savollar va o'qish maslahatlari uchun murojaat qiling.\n\n"
        "❓ Savolingizni yozing:\n"
        f"<i>(Chiqish uchun \"{CHIQISH_MATNI}\" tugmasini bosing)</i>",
        parse_mode="HTML",
        reply_markup=chat_keyboard(),
    )


@router.message(ChatbotState.chat_rejimi, F.text == CHIQISH_MATNI)
async def chatbot_chiqish(message: Message, state: FSMContext):
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

    data = await state.get_data()
    history: list[dict] = data.get("history", [])
    talaba: Optional[dict] = data.get("talaba")

    wait_msg = await message.answer("⏳ Javob tayyorlanmoqda...")

    javob = await gemini_javob_ol(history, savol)

    try:
        await wait_msg.delete()
    except Exception:
        pass

    if not javob:
        await message.answer(
            "❌ <b>Javob olishda xatolik yuz berdi.</b>\n\n"
            "Sabab bo'lishi mumkin:\n"
            "• Internet ulanishi muammosi\n"
            "• API kaliti noto'g'ri\n"
            "• Servis vaqtincha ishlamayapti\n\n"
            "<i>Qayta urinib ko'ring yoki adminga xabar bering.</i>",
            parse_mode="HTML",
        )
        return

    try:
        await message.answer(f"🤖 {javob}", parse_mode="HTML")
    except Exception:
        await message.answer(f"🤖 {javob}")

    history.append({"role": "user", "content": savol})
    history.append({"role": "assistant", "content": javob})
    if len(history) > MAX_HISTORY * 2:
        history = history[-(MAX_HISTORY * 2):]
    await state.update_data(history=history)

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
