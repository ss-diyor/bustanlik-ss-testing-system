import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import (
    init_db, add_user, talaba_topish, talaba_user_id_yangila,
    get_setting, guruh_qosh, get_user, update_user_phone,
)
from aiogram import F
from keyboards import user_menu_keyboard, oqituvchi_menu_keyboard, admin_menu_keyboard, phone_number_keyboard
import admin
import student
import email_broadcast

# ── Discord notify moduli ─────────────────────────────────────
from discord_notify import (
    notify_bot_started,
    notify_daily_ranking,
    notify_backup_sent,
    notify_error,
)

# Loglarni konsolga chiqaradi
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Bot va Dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Routerlarni ulash
dp.include_router(admin.router)
dp.include_router(student.router)
dp.include_router(email_broadcast.router)


@dp.message(CommandStart())
async def start_handler(message: Message):
    """/start buyrug'i"""
    user = get_user(message.from_user.id)

    # Agar foydalanuvchi birinchi marta kirayotgan bo'lsa yoki telefon raqami bo'lmasa
    if not user or not user.get('phone_number'):
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
        await message.answer(f"👋 Xush kelibsiz, Admin!", reply_markup=admin_menu_keyboard())
        return

    # O'qituvchi tekshiruvi
    teacher = oqituvchi_ol(message.from_user.id)
    if teacher:
        await message.answer(
            f"👋 Xush kelibsiz, {teacher['ismlar']}! ({teacher['sinf']} sinf rahbari)",
            reply_markup=oqituvchi_menu_keyboard(),
        )
        return

    ranking_enabled   = get_setting('ranking_enabled',   'True')
    stats_enabled     = get_setting('stats_enabled',     'True')
    chatbot_enabled   = get_setting('chatbot_enabled',   'True')
    mock_enabled      = get_setting('mock_enabled',      'True')
    quiz_enabled      = get_setting('quiz_enabled',      'True')
    mini_test_enabled = get_setting('mini_test_enabled', 'True')

    await message.answer(
        "👋 <b>Assalomu alaykum! Bo'stonliq tuman ixtisoslashtirilgan maktabining DTM Natijalar Botiga xush kelibsiz!</b>\n\n"
        "📌 <b>O'quvchilar uchun:</b>\n"
        "Shaxsiy kodingizni yuboring — natijangiz darhol taqdim etiladi.\n"
        "<i>Masalan: A-007 yoki 52B</i>\n\n"
        "🔗 <b>Profilingizni ulash:</b>\n"
        "Avtomatik xabarnoma olish uchun <code>ULASH_KODINGIZ</code> deb yozing.\n"
        "<i>Masalan: ULASH_1001</i>\n\n"
        "🔑 <b>Admin uchun:</b>\n"
        "/admin buyrug'ini yozing.",
        parse_mode="HTML",
        reply_markup=user_menu_keyboard(
            ranking_enabled,
            stats_enabled,
            chatbot_enabled,
            mock_enabled,
            quiz_enabled,
            mini_test_enabled,
        ),
    )


@dp.message(F.contact)
async def contact_handler(message: Message):
    """Telefon raqamini qabul qilish"""
    phone_number = message.contact.phone_number
    if not phone_number.startswith("+"):
        phone_number = "+" + phone_number
    update_user_phone(message.from_user.id, phone_number)
    await message.answer("✅ Telefon raqamingiz muvaffaqiyatli saqlandi!", reply_markup=ReplyKeyboardRemove())
    await start_handler(message)


@dp.message(F.text == "❌ Bekor qilish")
async def cancel_handler(message: Message):
    await message.answer("❌ Amallar bekor qilindi.", reply_markup=ReplyKeyboardRemove())


@dp.message(F.text == "🚪 Chiqish")
async def logout_handler(message: Message):
    """O'quvchi shaxsiy kabinetidan chiqish"""
    from database import get_connection, release_connection
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("UPDATE talabalar SET user_id = NULL WHERE user_id = %s", (message.from_user.id,))
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


@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: Message):
    """Guruhga bot qo'shilganda yoki xabar yozilganda guruhni bazaga qo'shadi."""
    guruh_qosh(message.chat.id, message.chat.title)


@dp.message(F.text.startswith("ULASH_"))
async def bind_user_to_kod(message: Message):
    kod    = message.text.replace("ULASH_", "").strip().upper()
    talaba = talaba_topish(kod)
    if talaba:
        talaba_user_id_yangila(kod, message.from_user.id)
        await message.answer(
            f"✅ Tabriklaymiz! Sizning profilingiz <b>{kod}</b> kodiga muvaffaqiyatli ulandi. "
            f"Endi yangi natijalar haqida avtomatik xabar olasiz.",
            parse_mode="HTML",
        )
    else:
        await message.answer("❌ Bunday kod topilmadi.")


# ──────────────────────────────────────────────────────────────
# Backup scheduler  →  har kuni soat 23:00
# ──────────────────────────────────────────────────────────────
async def send_backup():
    """Bazani backup qilish, adminlarga va Discord ga yuborish."""
    from config import ADMIN_IDS
    from database import get_all_students_for_excel
    import pandas as pd

    data = get_all_students_for_excel()
    if not data:
        return

    df       = pd.DataFrame(data)
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(filename, index=False)

    # Telegram adminlarga yuborish
    for admin_id in ADMIN_IDS:
        try:
            from aiogram.types import FSInputFile
            await bot.send_document(
                admin_id,
                FSInputFile(filename),
                caption=f"📅 Kundalik zaxira nusxa (Backup)\nSana: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            )
        except Exception as e:
            logging.error(f"Backup yuborishda xato (Admin: {admin_id}): {e}")

    # ── Discord bildirishnoma ─────────────────────────────────
    try:
        await notify_backup_sent(student_count=len(data), filename=filename)
    except Exception as e:
        logging.warning(f"Discord backup notify xatosi: {e}")
    # ─────────────────────────────────────────────────────────

    if os.path.exists(filename):
        os.remove(filename)


# ──────────────────────────────────────────────────────────────
# Reminder scheduler  →  har 60 soniyada tekshiradi
# ──────────────────────────────────────────────────────────────
async def reminder_scheduler():
    """Eslatmalarni tekshirib yuborish."""
    from database import kutilayotgan_reminders_ol, reminder_holat_yangila, get_all_user_ids
    while True:
        try:
            reminders = kutilayotgan_reminders_ol()
            for r in reminders:
                user_ids = get_all_user_ids()
                for uid in user_ids:
                    try:
                        await bot.send_message(uid, f"⏰ <b>ESLATMA:</b>\n\n{r['xabar']}", parse_mode="HTML")
                    except Exception:
                        pass
                reminder_holat_yangila(r['id'], 'yuborildi')
        except Exception as e:
            logging.error(f"Reminder scheduler error: {e}")
        await asyncio.sleep(60)


# ──────────────────────────────────────────────────────────────
# Reyting scheduler  →  har kuni soat 20:00
# ──────────────────────────────────────────────────────────────
async def group_ranking_scheduler():
    """Guruhlarga va Discordga har kuni soat 20:00 da Top-10 reyting yuborish."""
    from database import guruhlar_ol, sinf_ol, get_all_in_class
    while True:
        now = datetime.now()
        if now.hour == 20 and now.minute == 0:
            guruhlar = guruhlar_ol()
            sinflar  = sinf_ol()

            if sinflar:
                text = "🏆 <b>Bugungi Top-10 reytingi (Sinflar kesimida):</b>\n\n"
                discord_text = "**🏆 Bugungi Top-10 Reyting**\n\n"
                total_students = 0

                for s in sinflar:
                    talabalar = get_all_in_class(s)
                    if talabalar:
                        text         += f"📍 <b>{s} sinf:</b>\n"
                        discord_text += f"**📍 {s} sinf:**\n"
                        for i, t in enumerate(talabalar[:10], 1):
                            text         += f"  {i}. {t['ismlar']} — {t['umumiy_ball']} ball\n"
                            discord_text += f"  {i}. {t['ismlar']} — {t['umumiy_ball']} ball\n"
                            total_students += 1
                        text         += "\n"
                        discord_text += "\n"

                # Telegram guruhlariga yuborish
                for g in guruhlar:
                    try:
                        await bot.send_message(g['chat_id'], text, parse_mode="HTML")
                    except Exception:
                        pass

                # ── Discord bildirishnoma ─────────────────────────
                try:
                    await notify_daily_ranking(
                        ranking_text=discord_text,
                        total_students=total_students,
                    )
                except Exception as e:
                    logging.warning(f"Discord ranking notify xatosi: {e}")
                # ─────────────────────────────────────────────────

            await asyncio.sleep(61)
        await asyncio.sleep(30)


# ──────────────────────────────────────────────────────────────
# Backup vaqt scheduler  →  har kuni soat 23:00
# ──────────────────────────────────────────────────────────────
async def scheduler():
    """Har kuni soat 23:00 da backup yuborish."""
    while True:
        now = datetime.now()
        if now.hour == 23 and now.minute == 0:
            await send_backup()
            await asyncio.sleep(61)
        await asyncio.sleep(30)


# ──────────────────────────────────────────────────────────────
# main()
# ──────────────────────────────────────────────────────────────
async def main():
    """Botni ishga tushiradi."""
    init_db()
    logging.info("Ma'lumotlar bazasi tayyor va indekslar tekshirildi.")

    from database import create_admin_sessions_table, create_admins_table
    try:
        create_admin_sessions_table()
        create_admins_table()
        logging.info("Admin jadvallari yaratildi yoki allaqachon mavjud.")
    except Exception as e:
        logging.error(f"Admin jadvallarini yaratishda xato: {e}")

    # Schedulerlarni ishga tushirish
    asyncio.create_task(scheduler())
    asyncio.create_task(reminder_scheduler())
    asyncio.create_task(group_ranking_scheduler())

    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot ishga tushdi!")

    # ── Discord: bot ishga tushganda xabar ───────────────────
    try:
        await notify_bot_started()
    except Exception as e:
        logging.warning(f"Discord bot-start notify xatosi: {e}")
    # ─────────────────────────────────────────────────────────

    await dp.start_polling(
        bot,
        handle_signals=False,
        allowed_updates=["message", "callback_query", "edited_message", "inline_query"],
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi!")
