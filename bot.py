import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import admin, student

# Loglarni konsolga chiqaradi — xatolarni tezda topish uchun
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Bot va Dispatcher — MemoryStorage FSM holatlarini xotirada saqlaydi.
# Bot o'chsa holatlar yo'qoladi, bu bizning holatimizda muammo emas.
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Routerlarni ulash — tartib muhim!
# Admin handlerlari birinchi ulanadi, chunki ular aniq filtrlar bilan ishlaydi.
# Student handleri oxirida ulanadi — u hamma narsani "ushlab oluvchi" (catch-all).
dp.include_router(admin.router)
dp.include_router(student.router)


@dp.message(CommandStart())
async def start_handler(message: Message):
    """
    /start buyrug'i — botni birinchi ochganda chiqadigan xabar.
    Ikki guruh uchun turlicha yo'llanma beradi.
    """
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
    # Bazani ishga tushiradi (agar jadvallar yo'q bo'lsa yaratadi)
    init_db()
    logging.info("Ma'lumotlar bazasi tayyor.")

    # Botni polling rejimida ishga tushiradi
    # skip_updates=True — bot o'chib turgan vaqtdagi xabarlarni o'tkazib yuboradi
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
