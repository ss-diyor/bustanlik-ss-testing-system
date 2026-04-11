from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database import talaba_topish, kalit_ol

router = Router()

def solishtir(asl, foydalanuvchi):
    """Ikkita javoblar qatorini solishtiradi."""
    xatolar = []
    togri = 0
    # Faqat eng qisqa uzunlik bo'yicha solishtiramiz
    uzunlik = min(len(asl), len(foydalanuvchi))
    for i in range(uzunlik):
        if asl[i] == foydalanuvchi[i]:
            togri += 1
        else:
            xatolar.append(i + 1)
    return togri, xatolar

@router.message(F.text & ~F.text.startswith("/"))
async def talaba_natija(message: Message, state: FSMContext):
    """
    O'quvchi kodi yoki javoblar qatorini tekshirish.
    """
    text = message.text.strip().upper()
    
    # Agar bu 6 belgili kod bo'lsa (shaxsiy kod)
    if len(text) == 6 and any(c.isdigit() for c in text):
        talaba = talaba_topish(text)
        if not talaba:
            await message.answer(f"❌ <b>{text}</b> kodi topilmadi.", parse_mode="HTML")
            return

        # Natijani ko'rsatish
        res_text = (f"🎓 <b>Sizning natijangiz</b>\n\n"
                    f"👤 Kod: <b>{talaba['kod']}</b>\n"
                    f"🎯 Yo'nalish: <b>{talaba['yonalish']}</b>\n\n"
                    f"📊 <b>Natijalar:</b>\n"
                    f"  📘 Majburiy: {talaba['majburiy']}/30 ta\n"
                    f"  📗 1-Asosiy: {talaba['asosiy_1']}/30 ta\n"
                    f"  📙 2-Asosiy: {talaba['asosiy_2']}/30 ta\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"🏆 <b>Umumiy ball: {talaba['umumiy_ball']} / 189</b>")
        
        # Agar admin kalitlarni kiritgan bo'lsa, xatolarni ham ko'rsatish taklifi
        kalitlar = kalit_ol(talaba['yonalish'])
        if kalitlar:
            res_text += f"\n\nℹ️ <i>Xatolaringizni bilish uchun javoblaringizni quyidagi formatda yuboring:</i>\n<code>javob:majburiy,asosiy1,asosiy2</code>\n<i>Masalan: javob:abcd...,abcd...,abcd...</i>"
            
        await message.answer(res_text, parse_mode="HTML")
        return

    # Agar foydalanuvchi javoblarini tekshirmoqchi bo'lsa (format: javob:m,a1,a2)
    if text.startswith("JAVOB:"):
        try:
            parts = text.replace("JAVOB:", "").split(",")
            if len(parts) != 3:
                await message.answer("❌ Xato format! Iltimos, javoblarni vergul bilan ajratib yuboring.\nMasalan: <code>javob:abcd...,abcd...,abcd...</code>", parse_mode="HTML")
                return
            
            # Bu yerda o'quvchi avval o'z kodini kiritgan bo'lishi kerak yoki bizga yo'nalish kerak
            await message.answer("🔍 Xatolarni aniqlash uchun avval shaxsiy kodingizni yuboring, keyin javoblarni tekshiramiz.")
        except:
            await message.answer("❌ Xatolik yuz berdi. Formatni tekshiring.")
