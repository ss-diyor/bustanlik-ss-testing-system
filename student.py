from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database import talaba_topish

router = Router()


@router.message(F.text & ~F.text.startswith("/"))
async def talaba_natija(message: Message, state: FSMContext):
    """
    Admin rejimida bo'lmagan har qanday matn — o'quvchi kodi deb qabul qilinadi.
    Bot shu kod bo'yicha bazadan natijani qidiradi.
    """
    # Agar foydalanuvchi admin menyu tugmalarini bossa, bu handlerga tushmasin
    # (admin handlerlari avval ishlaydi, chunki ular aniq F.text filtrlarga ega)
    # Shuning uchun bu handler hech qanday tugma matnini ushlamasligi kerak
    admin_tugmalar = [
        "➕ O'quvchi qo'shish", "✏️ Natijani tahrirlash",
        "📊 Statistika", "🔍 Kod bo'yicha qidirish", "🚪 Chiqish"
    ]
    if message.text in admin_tugmalar:
        return  # bu xabar admin handler tomonidan boshqariladi

    kod = message.text.strip().upper()
    talaba = talaba_topish(kod)

    if not talaba:
        await message.answer(
            f"❌ <b>{kod}</b> kodi topilmadi.\n\n"
            f"Iltimos, kodingizni to'g'ri kiriting.\n"
            f"Masalan: <code>A-001</code> yoki <code>52B</code>",
            parse_mode="HTML"
        )
        return

    # Ball foizi (189 dan necha foiz)
    foiz = round((talaba['umumiy_ball'] / 189) * 100, 1)

    # Natijani chiroyli formatda ko'rsatadi
    await message.answer(
        f"🎓 <b>Sizning natijangiz</b>\n\n"
        f"👤 Kod: <b>{talaba['kod']}</b>\n"
        f"🎯 Yo'nalish: <b>{talaba['yonalish']}</b>\n\n"
        f"📊 <b>Fan bo'yicha natijalar:</b>\n"
        f"  📘 Majburiy fanlar: {talaba['majburiy']}/30 ta → <b>{talaba['majburiy'] * 1.1:.1f}</b> ball\n"
        f"  📗 1-asosiy fan:    {talaba['asosiy_1']}/30 ta → <b>{talaba['asosiy_1'] * 3.1:.1f}</b> ball\n"
        f"  📙 2-asosiy fan:    {talaba['asosiy_2']}/30 ta → <b>{talaba['asosiy_2'] * 2.1:.1f}</b> ball\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Umumiy ball: {talaba['umumiy_ball']} / 189</b>\n"
        f"📈 Foiz: <b>{foiz}%</b>",
        parse_mode="HTML"
    )
