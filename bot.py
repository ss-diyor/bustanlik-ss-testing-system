import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db, add_user, talaba_topish, talaba_user_id_yangila, get_setting
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
dp.include_router(student.router)
dp.include_router(admin.router)


@dp.message(CommandStart())
async def start_handler(message: Message):
    """/start buyrug'i"""
    # add_user endi pool orqali tezroq ishlaydi
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    
    # Admin tekshiruvi
    from admin import is_admin_id
    from database import oqituvchi_ol
    if is_admin_id(message.from_user.id):
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
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot ishga tushdi!")
    
    # Fast polling config
    await dp.start_polling(bot, handle_signals=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi!")
