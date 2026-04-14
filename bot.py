import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db, add_user, talaba_topish, talaba_user_id_yangila
from aiogram import F
from keyboards import user_menu_keyboard
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
async def start_handler(message: Message):
    """/start buyrug'i"""
    # add_user endi pool orqali tezroq ishlaydi
    add_user(message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name)
    await message.answer(
        "👋 <b>Assalomu alaykum! Bo'stonliq tuman ixtisoslashtirilgan maktabi DTM Natijalar Botiga xush kelibsiz!</b>\n\n"
        "📌 <b>O'quvchilar uchun:</b>\n"
        "Shaxsiy kodingizni yuboring — natijangiz darhol yuboriladi.\n"
        "<i>Masalan: A-007 yoki 52B</i>\n\n"
        "🔗 <b>Profilingizni ulash:</b>\n"
        "Avtomatik xabarnoma olish uchun <code>ULASH_KODINGIZ</code> deb yozing.\n"
        "<i>Masalan: ULASH_1001</i>\n\n"
        "🔑 <b>Admin uchun:</b>\n"
        "/admin buyrug'ini yozing.",
        parse_mode="HTML",
        reply_markup=user_menu_keyboard()
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


async def main():
    """Botni ishga tushiradi."""
    # Bazani ishga tushiradi
    init_db()
    logging.info("Ma'lumotlar bazasi tayyor va indekslar tekshirildi.")

    # Botni polling rejimida ishga tushiradi
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot ishga tushdi!")
    
    # Fast polling config
    await dp.start_polling(bot, handle_signals=False)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi!")
