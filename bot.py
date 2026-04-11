import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
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
    await message.answer(
        "👋 <b>DTM Natijalar Botiga xush kelibsiz!</b>\n\n"
        "📌 <b>O'quvchilar uchun:</b>\n"
        "Shaxsiy kodingizni yuboring — natijangiz darhol ko'rsatiladi.\n"
        "<i>Masalan: A-001 yoki 52B</i>\n\n"
        "🔑 <b>Admin uchun:</b>\n"
        "/admin buyrug'ini yozing.",
        parse_mode="HTML"
    )


async def main():
    """Botni ishga tushiradi."""
    # Bazani ishga tushiradi
    init_db()
    logging.info("Ma'lumotlar bazasi tayyor.")

    # Botni polling rejimida ishga tushiradi
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
