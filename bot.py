import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN
from database import init_db, add_user, talaba_topish, talaba_user_id_yangila, get_setting, guruh_qosh
from aiogram import F
from keyboards import user_menu_keyboard, oqituvchi_menu_keyboard, admin_menu_keyboard
import admin
import student

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


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    """/start buyrug'i"""
    # add_user endi pool orqali tezroq ishlaydi
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    
    # Admin tekshiruvi
    from admin import is_admin_id
    from database import oqituvchi_ol
    if is_admin_id(message.from_user.id):
        await state.update_data(admin=True)  # ← TUZATISH: state ga admin=True saqlanadi
        await message.answer(f"👋 Xush kelibsiz, Admin!", reply_markup=admin_menu_keyboard())
        return

    # O'qituvchi tekshiruvi
    teacher = oqituvchi_ol(message.from_user.id)
    if teacher:
        await message.answer(f"👋 Xush kelibsiz, {teacher['ismlar']}! ({teacher['sinf']} sinf rahbari)", reply_markup=oqituvchi_menu_keyboard())
        return

    ranking_enabled = get_setting('ranking_enabled', 'True')
    stats_enabled = get_setting('stats_enabled', 'True')
    
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
        reply_markup=user_menu_keyboard(ranking_enabled, stats_enabled)
    )

@dp.message(F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(message: Message):
    """Guruhga bot qo'shilganda yoki xabar yozilganda guruhni bazaga qo'shadi."""
    guruh_qosh(message.chat.id, message.chat.title)

@dp.message(F.text.startswith("ULASH_"))
async def bind_user_to_kod(message: Message):
    kod = message.text.replace("ULASH_", "").strip().upper()
    talaba = talaba_topish(kod)
    if talaba:
        talaba_user_id_yangila(kod, message.from_user.id)
        await message.answer(f"✅ Tabriklaymiz! Sizning profilingiz <b>{kod}</b> kodiga muvaffaqiyatli ulandi. Endi yangi natijalar haqida avtomatik xabar olasiz.", parse_mode="HTML")
    else:
        await message.answer("❌ Bunday kod topilmadi.")


async def send_backup():
    """Bazani backup qilish va adminlarga yuborish."""
    from config import ADMIN_IDS
    from database import get_all_students_for_excel
    import pandas as pd
    
    data = get_all_students_for_excel()
    if not data: return
    
    df = pd.DataFrame(data)
    filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(filename, index=False)
    
    for admin_id in ADMIN_IDS:
        try:
            from aiogram.types import FSInputFile
            await bot.send_document(admin_id, FSInputFile(filename), caption=f"📅 Kundalik zaxira nusxa (Backup)\nSana: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        except Exception as e:
            logging.error(f"Backup yuborishda xato (Admin: {admin_id}): {e}")
    
    if os.path.exists(filename): os.remove(filename)

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

async def group_ranking_scheduler():
    """Guruhlarga har kuni soat 20:00 da barcha sinflar bo'yicha Top-10 reyting yuborish."""
    from database import guruhlar_ol, sinf_ol, get_all_in_class
    while True:
        now = datetime.now()
        if now.hour == 20 and now.minute == 0:
            guruhlar = guruhlar_ol()
            sinflar = sinf_ol()
            
            if sinflar:
                text = "🏆 <b>Bugungi Top-10 reytingi (Sinflar kesimida):</b>\n\n"
                for s in sinflar:
                    talabalar = get_all_in_class(s)
                    if talabalar:
                        text += f"📍 <b>{s} sinf:</b>\n"
                        for i, t in enumerate(talabalar[:10], 1):
                            text += f"  {i}. {t['ismlar']} — {t['umumiy_ball']} ball\n"
                        text += "\n"
                
                for g in guruhlar:
                    try:
                        await bot.send_message(g['chat_id'], text, parse_mode="HTML")
                    except Exception:
                        pass
            await asyncio.sleep(61)
        await asyncio.sleep(30)

async def scheduler():
    """Har kuni soat 23:00 da backup yuborish."""
    while True:
        now = datetime.now()
        # Soat 23:00 da ishga tushadi
        if now.hour == 23 and now.minute == 0:
            await send_backup()
            await asyncio.sleep(61) # Bir marta ishlashi uchun
        await asyncio.sleep(30)

async def main():
    """Botni ishga tushiradi."""
    # Bazani ishga tushiradi
    init_db()
    logging.info("Ma'lumotlar bazasi tayyor va indekslar tekshirildi.")
    
    # Scheduler ishga tushirish
    asyncio.create_task(scheduler())
    asyncio.create_task(reminder_scheduler())
    asyncio.create_task(group_ranking_scheduler())
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot ishga tushdi!")
    
    # Fast polling config
    await dp.start_polling(bot, handle_signals=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi!")
