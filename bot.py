import asyncio
import logging
import os
import psycopg2.extras
from datetime import datetime
from tz_utils import now as tz_now, TZ

from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardRemove, ChatMemberUpdated
from aiogram.filters import CommandStart, ChatMemberUpdatedFilter, JOIN_TRANSITION
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from webapp.server import start_web_server
from database import (
    init_db,
    add_user,
    talaba_topish,
    talaba_user_id_yangila,
    get_setting,
    guruh_qosh,
    get_user,
    update_user_phone,
    is_notification_enabled,
)
from aiogram import F
from keyboards import (
    user_menu_keyboard,
    oqituvchi_menu_keyboard,
    admin_menu_keyboard,
    phone_number_keyboard,
)
import admin
import student
import mock_admin
import mock_excel_import
import mock_student
import language_handlers
import parent
import chatbot
import group_commands
import practice_quiz
import mini_test_handler
import cert_admin

# Loglarni konsolga chiqaradi
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import ClientTimeout

# Bot va Dispatcher (Timeoutni 5 minutga oshiramiz - importlar uchun)
session = AiohttpSession(timeout=300)
bot = Bot(token=BOT_TOKEN, session=session)
dp = Dispatcher(storage=MemoryStorage())

# ── Rate Limiter — spam himoyasi ──────────────────────────────────────────
from rate_limiter import rate_limiter
dp.update.middleware(rate_limiter)

# Routerlarni ulash
dp.include_router(admin.router)
dp.include_router(mock_admin.router)
dp.include_router(mock_excel_import.router)
dp.include_router(chatbot.router)
dp.include_router(student.router)
dp.include_router(mock_student.router)
dp.include_router(language_handlers.router)
dp.include_router(parent.router)
dp.include_router(group_commands.router)
dp.include_router(practice_quiz.router)
dp.include_router(mini_test_handler.router)
dp.include_router(cert_admin.router)


@dp.message(CommandStart())
async def start_handler(message: Message):
    """/start buyrug'i"""
    user = get_user(message.from_user.id)

    # Agar foydalanuvchi birinchi marta kirayotgan bo'lsa yoki telefon raqami bo'lmasa
    if not user or not user.get("phone_number"):
        add_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
        await message.answer(
            "📱 <b>Telefon raqamingizni yuboring:</b>\n\n"
            "Quyidagi tugmani bosib avtomatik yuborishingiz yoki qo'lda kiritishingiz mumkin.\n"
            "Format: +998901234567",
            parse_mode="HTML",
            reply_markup=phone_number_keyboard(),
        )
        return

    # Admin tekshiruvi
    from admin import is_admin_id
    from database import oqituvchi_ol

    if is_admin_id(message.from_user.id):
        await message.answer(
            f"👋 Xush kelibsiz, Admin!", reply_markup=admin_menu_keyboard()
        )
        return

    # O'qituvchi tekshiruvi
    teacher = oqituvchi_ol(message.from_user.id)
    if teacher:
        await message.answer(
            f"👋 Xush kelibsiz, {teacher['ismlar']}! ({teacher['sinf']} sinf rahbari)",
            reply_markup=oqituvchi_menu_keyboard(),
        )
        return

    ranking_enabled = get_setting("ranking_enabled", "True")
    stats_enabled = get_setting("stats_enabled", "True")
    chatbot_enabled = get_setting("chatbot_enabled", "True")
    mock_enabled = get_setting("mock_enabled", "True")
    quiz_enabled = get_setting("quiz_enabled", "True")
    mini_test_enabled = get_setting("mini_test_enabled", "True")

    await message.answer(
        "👋 <b>Assalomu alaykum! Bo'stonliq tuman ixtisoslashtirilgan maktabining DTM imtihoni va mock testlar natijalari botiga xush kelibsiz!</b>\n\n"
        "📌 <b>O'quvchilar uchun:</b>\n"
        "Shaxsiy kodingizni yuboring — natijangiz darhol ko'rsatiladi.\n"
        "<i>Masalan: A-007 yoki 52B</i>\n\n"
        "👨‍👩‍👦 <b>Ota-onalar uchun:</b>\n"
        "Farzandingizni ulash: <code>PARENT_KODINGIZ</code>\n"
        "<i>Masalan: PARENT_A007</i>\n\n"
        "🔗 <b>Profilni ulash:</b>\n"
        "Avtomatik xabarnoma uchun <code>ULASH_KODINGIZ</code> deb yozing.",
        parse_mode="HTML",
        reply_markup=user_menu_keyboard(ranking_enabled, stats_enabled, chatbot_enabled, mock_enabled, quiz_enabled, mini_test_enabled),
    )


@dp.message(F.contact)
async def contact_handler(message: Message):
    """Telefon raqamini qabul qilish"""
    phone_number = message.contact.phone_number
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number

    update_user_phone(message.from_user.id, phone_number)
    await message.answer(
        "✅ Telefon raqamingiz muvaffaqiyatli saqlandi!",
        reply_markup=ReplyKeyboardRemove(),
    )
    # Guruhlarga yangi foydalanuvchi haqida xabar yuborish
    asyncio.create_task(
        _guruh_royxat_bildirish(
            message.bot,
            tg_user=message.from_user,
            phone_number=phone_number,
        )
    )
    await start_handler(message)


@dp.message(F.text == "❌ Bekor qilish")
async def cancel_handler(message: Message):
    await message.answer(
        "❌ Amallar bekor qilindi.", reply_markup=ReplyKeyboardRemove()
    )


@dp.message(F.text == "🚪 Chiqish")
async def logout_handler(message: Message):
    """O'quvchi shaxsiy kabinetidan chiqish"""
    from database import get_connection, release_connection

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE talabalar SET user_id = NULL WHERE user_id = %s",
        (message.from_user.id,),
    )
    conn.commit()
    cur.close()
    release_connection(conn)

    await message.answer(
        "🚪 <b>Siz shaxsiy kabinetdan chiqdingiz.</b>\n\n"
        "Qayta kirish uchun shaxsiy kodingizni yuboring yoki <code>ULASH_KOD</code> buyrug'idan foydalaning.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    await start_handler(message)


# ── TUZATISH 1: Bot guruhga qo'shilganda avtomatik ro'yxatdan o'tkazish ──────
@dp.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def bot_added_to_group(event: ChatMemberUpdated):
    """Bot guruhga qo'shilganda guruhni bazaga saqlaydi."""
    if event.chat.type in ("group", "supergroup"):
        guruh_qosh(event.chat.id, event.chat.title)
        logger.info(
            f"Bot guruhga qo'shildi va saqlandi: '{event.chat.title}' (ID: {event.chat.id})"
        )


# ── TUZATISH 2: Guruhda xabar yozilganda ham yangilash (chat_id o'zgarishi uchun) ──
@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: Message):
    """Guruhda xabar yozilganda guruhni bazaga qo'shadi/yangilaydi."""
    guruh_qosh(message.chat.id, message.chat.title)


@dp.message(F.text.startswith("ULASH_"))
async def bind_user_to_kod(message: Message):
    from database import demo_sessiya_boshlash, demo_kodlar_ol
    kod = message.text.replace("ULASH_", "").strip().upper()
    talaba = talaba_topish(kod)
    if talaba:
        # ── Demo kod tekshiruvi ────────────────────────────────────────────
        if talaba.get("is_demo"):
            demo_sessiya_boshlash(message.from_user.id, kod)
            await message.answer(
                "🎭 <b>Demo rejimga xush kelibsiz!</b>\n\n"
                f"📌 Sizning demo kodingiz: <code>{kod}</code>\n\n"
                "Botning barcha funksiyalarini sinab ko'rishingiz mumkin.\n"
                "<i>Bu vaqtinchalik demo — haqiqiy kodingiz tayyor bo'lgach, uni yuboring.</i>",
                parse_mode="HTML",
                reply_markup=user_menu_keyboard(
                    get_setting("ranking_enabled", "True"),
                    get_setting("stats_enabled", "True"),
                    get_setting("chatbot_enabled", "True"),
                    get_setting("mock_enabled", "True"),
                    get_setting("quiz_enabled", "True"),
                    get_setting("mini_test_enabled", "True"),
                ),
            )
            return

        # ── Oddiy talaba ulash ─────────────────────────────────────────────
        avval_ulangan = talaba.get("user_id") is not None
        talaba_user_id_yangila(kod, message.from_user.id)
        await message.answer(
            f"✅ Tabriklaymiz! Sizning profilingiz <b>{kod}</b> kodiga muvaffaqiyatli ulandi. Endi yangi natijalar haqida avtomatik xabar olasiz.",
            parse_mode="HTML",
        )
        if not avval_ulangan:
            asyncio.create_task(
                _guruh_royxat_bildirish(message.bot, tg_user=message.from_user, talaba=talaba)
            )
    else:
        await message.answer("❌ Bunday kod topilmadi.")


async def _guruh_royxat_bildirish(
    bot: Bot,
    tg_user,
    talaba: dict = None,
    phone_number: str = None,
):
    """Guruhlarga yangi foydalanuvchi haqida xabar yuboradi.

    - phone_number berilsa: telefon orqali ro'yxatdan o'tish
    - talaba berilsa: ULASH_KOD orqali akkaunt ulash
    """
    from database import guruhlar_ol

    guruhlar = guruhlar_ol()
    if not guruhlar:
        logger.warning("Guruhlar ro'yxati bo'sh — xabar yuborilmadi.")
        return

    username = f"@{tg_user.username}" if tg_user.username else "—"
    full_name = tg_user.full_name or "—"

    if phone_number and talaba is None:
        # Faqat telefon raqam ulashgan — hali kod bilan ulanmagan
        text = (
            f"📱 <b>Yangi foydalanuvchi ro'yxatdan o'tdi!</b>\n\n"
            f"👤 Ism: <b>{full_name}</b>\n"
            f"📞 Telefon: <b>{phone_number}</b>\n"
            f"🔗 Telegram: {username}\n\n"
            f"<i>Hali talaba kodi bilan ulanmagan</i>"
        )
    else:
        # ULASH_KOD orqali talaba profili ulandi
        text = (
            f"🎉 <b>Yangi o'quvchi ro'yxatdan o'tdi!</b>\n\n"
            f"👤 Ism: <b>{talaba['ismlar']}</b>\n"
            f"🆔 Kod: <b>{talaba['kod']}</b>\n"
            f"🏫 Sinf: <b>{talaba.get('sinf', '—')}</b>\n"
            f"🎯 Yo'nalish: <b>{talaba.get('yonalish', '—')}</b>\n"
            f"📞 Telefon: <b>{phone_number or '—'}</b>\n"
            f"🔗 Telegram: {username}"
        )

    # ── TUZATISH 3: Xatolarni log qilish, sukut bilan o'tkazmaslik ──────────
    for g in guruhlar:
        guruh_nomi = g.get("nomi") or "Nomsiz"
        try:
            await bot.send_message(g["chat_id"], text, parse_mode="HTML")
            logger.info("Guruhga xabar yuborildi: '%s' (ID: %s)", guruh_nomi, g["chat_id"])
        except Exception as e:
            logger.error(
                "Guruhga xabar yuborishda XATO — Guruh: '%s' (ID: %s) | Xato: %s",
                guruh_nomi, g["chat_id"], e
            )


async def send_backup():
    """Bazani backup qilish va adminlarga yuborish."""
    from config import ADMIN_IDS
    from database import get_all_students_for_excel
    import pandas as pd

    data = get_all_students_for_excel()
    if not data:
        return

    df = pd.DataFrame(data)
    filename = f"backup_{tz_now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(filename, index=False)

    for admin_id in ADMIN_IDS:
        try:
            from aiogram.types import FSInputFile

            await bot.send_document(
                admin_id,
                FSInputFile(filename),
                caption=f"📅 Kundalik zaxira nusxa (Backup)\nSana: {tz_now().strftime('%d.%m.%Y %H:%M')}",
            )
        except Exception as e:
            logging.error(f"Backup yuborishda xato (Admin: {admin_id}): {e}")

    if os.path.exists(filename):
        os.remove(filename)


async def reminder_scheduler():
    """Eslatmalarni tekshirib yuborish."""
    from database import (
        kutilayotgan_reminders_ol,
        reminder_holat_yangila,
        get_all_user_ids,
    )

    while True:
        try:
            reminders = kutilayotgan_reminders_ol()
            for r in reminders:
                user_ids = get_all_user_ids()
                for uid in user_ids:
                    if not is_notification_enabled(uid, "notify_reminders"):
                        continue
                    try:
                        await bot.send_message(
                            uid,
                            f"⏰ <b>ESLATMA:</b>\n\n{r['xabar']}",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                reminder_holat_yangila(r["id"], "yuborildi")
        except Exception as e:
            logging.error(f"Reminder scheduler error: {e}")
        await asyncio.sleep(60)


async def test_schedule_reminder_scheduler():
    """Ertangi yoki bugungi testlar haqida o'quvchilarga avtomatik eslatma yuborish."""
    from database import get_connection, release_connection, get_all_user_ids
    
    while True:
        try:
            now = tz_now()
            # Har kuni soat 08:00 da bugungi testlar haqida eslatma yuboramiz
            if now.hour == 8 and now.minute == 0:
                conn = get_connection()
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                
                # Bugungi testlarni olamiz
                cur.execute("SELECT * FROM test_taqvimi WHERE sana = CURRENT_DATE")
                today_tests = cur.fetchall()
                
                if today_tests:
                    user_ids = get_all_user_ids()
                    for test in today_tests:
                        text = (
                            f"📅 <b>BUGUN TEST BOR!</b>\n\n"
                            f"📝 Test: <b>{test['test_nomi']}</b>\n"
                            f"⏰ Vaqt: <b>{test['vaqt'] or 'Belgilanmagan'}</b>\n"
                            f"👥 Sinf: <b>{test['sinf'] or 'Barchaga'}</b>\n\n"
                            f"Barcha o'quvchilarga omad tilaymiz! 💪"
                        )
                        
                        for uid in user_ids:
                            if not is_notification_enabled(uid, "notify_reminders"):
                                continue
                            try:
                                await bot.send_message(uid, text, parse_mode="HTML")
                            except Exception:
                                pass
                                
                cur.close()
                release_connection(conn)
                await asyncio.sleep(61)
        except Exception as e:
            logging.error(f"Test schedule reminder error: {e}")
        await asyncio.sleep(30)


async def group_ranking_scheduler():
    """Guruhlarga har kuni soat 20:00 da barcha sinflar bo'yicha Top-10 reyting yuborish."""
    from database import guruhlar_ol, sinf_ol, get_all_in_class

    while True:
        now = tz_now()
        if now.hour == 20 and now.minute == 0:
            guruhlar = guruhlar_ol()
            sinflar = sinf_ol()

            if sinflar:
                text = (
                    "🏆 <b>Bugungi Top-10 reytingi (Sinflar kesimida):</b>\n\n"
                )
                for s in sinflar:
                    talabalar = get_all_in_class(s)
                    if talabalar:
                        text += f"📍 <b>{s} sinf:</b>\n"
                        for i, t in enumerate(talabalar[:10], 1):
                            text += f"  {i}. {t['ismlar']} — {t['umumiy_ball']} ball\n"
                        text += "\n"

                for g in guruhlar:
                    try:
                        await bot.send_message(
                            g["chat_id"], text, parse_mode="HTML"
                        )
                    except Exception as e:
                        guruh_nomi = g.get("nomi") or "Nomsiz"
                        logging.error(
                            "Reyting yuborishda xato — Guruh: '%s' (ID: %s) | Xato: %s",
                            guruh_nomi, g["chat_id"], e
                        )
            await asyncio.sleep(61)
        await asyncio.sleep(30)


async def scheduler():
    """Har kuni soat 04:00 da backup yuborish."""
    while True:
        now = tz_now()
        if now.hour == 4 and now.minute == 0:
            await send_backup()
            await asyncio.sleep(61)
        await asyncio.sleep(30)


async def main():
    """Botni ishga tushiradi."""
    import time
    from bot_status import set_start_time
    set_start_time(time.time())

    # ─── 1. Web server BIRINCHI bind bo'lishi kerak ───────────────────────────
    # Railway health check PORT ga ulanishga harakat qiladi. Agar web server
    # DB init tugaguncha ishga tushmasa, deploy muvaffaqiyatsiz bo'ladi.
    web_runner = await start_web_server(BOT_TOKEN)
    logging.info("Web server tayyor. DB init boshlandi...")

    # ─── 2. Ma'lumotlar bazasini sozlash ──────────────────────────────────────
    init_db()
    logging.info("Ma'lumotlar bazasi tayyor va indekslar tekshirildi.")

    from database import create_admin_sessions_table, create_admins_table

    try:
        create_admin_sessions_table()
        create_admins_table()
        from mock_database import create_mock_tables
        create_mock_tables()
        logging.info("Mock natijalari jadvali tayyor.")
        logging.info("Admin jadvallari yaratildi yoki allaqachon mavjud.")
    except Exception as e:
        logging.error(f"Admin jadvallarini yaratishda xato: {e}")

    try:
        from database import create_chatbot_logs_table
        create_chatbot_logs_table()
        logging.info("Chatbot logs jadvali tayyor.")
    except Exception as e:
        logging.error(f"Chatbot jadvali yaratishda xato: {e}")

    # ─── 3. Background tasklar ────────────────────────────────────────────────
    asyncio.create_task(scheduler())
    asyncio.create_task(reminder_scheduler())
    asyncio.create_task(test_schedule_reminder_scheduler())
    asyncio.create_task(group_ranking_scheduler())

    # ─── 4. Polling ───────────────────────────────────────────────────────────
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot ishga tushdi!")

    try:
        await dp.start_polling(
            bot,
            handle_signals=True,  # SIGTERM ni to'g'ri qayta ishlash (Railway)
            allowed_updates=[
                "message",
                "callback_query",
                "edited_message",
                "inline_query",
                "my_chat_member",   # ← TUZATISH 4: bot qo'shilishini kuzatish uchun
            ],
        )
    finally:
        # Graceful shutdown: web server va bot sessionni yoqamiz
        logging.info("Bot to'xtatilmoqda...")
        await bot.session.close()
        if web_runner:
            await web_runner.cleanup()
        logging.info("Tozalash tugadi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi!")
