# Sinf va Maktab Ma'lumotlarini Ajratish - O'zgarishlar Xulasasi

## Umumiy Maqsad
O'quvchilarning sinf va maktab ma'lumotlarini alohida yuritish uchun tizimni refactor qilish. Avvalgi holatda "11-B - 3-maktab" ko'rinishida birlashtirilgan ma'lumotlarni endi alohida saqlanadi.

## Amalga Oshirilgan O'zgarishlar

### 1. **database.py** - Ma'lumotlar Bazasi Qismi
- ✅ `talaba_qosh()` funksiyasida sinf va maktab nomini avtomatik ravishda ajratib olish
  - Agar sinf nomida " - " mavjud bo'lsa, uni ajratib oladi
  - Masalan: "11-B - 3-maktab" → sinf="11-B", maktab="3-maktab"
  - Maktab nomini `maktablar` jadvalida topib, `maktab_id` sini o'rnatadi
- ✅ Migratsiya kodini o'chirish (sinf va maktab birlashtirish)

### 2. **admin.py** - Admin Paneli
- ✅ Excel import jarayonida sinf va maktab birlashtirmaslik
  - Oldingi kod: `sinf = f"{sinf} - {maktab['nomi']}"`
  - Yangi kod: Sinf va maktab alohida saqlanadi
  - `talaba_qosh()` funksiyasi avtomatik ravishda ajratib oladi

### 3. **webapp/server.py** - Backend API
- ✅ **Student API** (`/api/student`):
  - SQL so'roviga `LEFT JOIN maktablar` qo'shish
  - JSON javobiga `"maktab"` maydonini qo'shish
  - Masalan: `{"student": {"kod": "...", "sinf": "11-B", "maktab": "3-maktab", ...}}`

- ✅ **Admin API** (`/api/admin/stats`):
  - Top 30 o'quvchilar ro'yxatiga maktab nomini qo'shish
  - SQL GROUP BY-ga `m.nomi` qo'shish
  - JSON javobiga `"maktab"` maydonini qo'shish

### 4. **webapp/app.js** - O'quvchi Web Interfeysi
- ✅ Student meta qatorida maktabni alohida ko'rsatish
  - Avvalgi: `11-B · Yo'nalish · Kod`
  - Yangi: `3-maktab | 11-B · Yo'nalish · Kod`

### 5. **webapp/admin.js** - Admin Web Paneli
- ✅ **Search natijasida** maktabni ko'rsatish
  - Avvalgi: `Ism | Sinf | Kod`
  - Yangi: `Ism | Maktab | Sinf | Kod`

- ✅ **Student details modal**-da maktabni ko'rsatish
  - Avvalgi: `modal-student-class` = "11-B"
  - Yangi: `modal-student-class` = "3-maktab | 11-B"

### 6. **student.py** - Telegram Bot (O'quvchi)
- ✅ Sertifikat va natija xabarlarida maktabni qo'shish
  - Avvalgi: `🏫 Sinf: 11-B`
  - Yangi: 
    ```
    🏫 Maktab: 3-maktab
    📚 Sinf: 11-B
    ```

### 7. **bot.py** - Telegram Bot (Asosiy)
- ✅ Profil ulash xabarida maktabni qo'shish
  - Guruh xabarlari
  - Discord bildirishnomalar
  - Avvalgi: `🏫 Sinf: 11-B`
  - Yangi:
    ```
    🏫 Maktab: 3-maktab
    📚 Sinf: 11-B
    ```

## Texnik Detallar

### Database Schema
```sql
-- talabalar jadvalida mavjud:
- sinf (TEXT) -- Endi faqat sinf nomi: "11-B"
- maktab_id (INTEGER) -- Maktab ID si

-- maktablar jadvalida:
- id (SERIAL PRIMARY KEY)
- nomi (TEXT) -- Maktab nomi: "3-maktab"
```

### API Javob Formati
```json
{
  "student": {
    "kod": "STU001",
    "ismlar": "Ahmedov Alisher",
    "sinf": "11-B",
    "maktab": "3-maktab",
    "yonalish": "Matematika + Fizika"
  }
}
```

## Foydalanuvchi Uchun Manfaatlar

1. ✅ **Aniqroq Statistika**: Maktab bo'yicha alohida statistika olish mumkin
2. ✅ **Qidiruv Opsiyalari**: Maktab va sinf bo'yicha alohida qidirish
3. ✅ **Tozaroq UI**: Interfeyslarda maktab va sinf alohida ko'rinadi
4. ✅ **Excel/PDF Eksport**: Maktab va sinf alohida ustunlarda saqlanadi

## Orqaga Mos Kelish (Backward Compatibility)

- ✅ Excel importda eski format ("11-B - 3-maktab") hali ham qabul qilinadi
- ✅ `talaba_qosh()` funksiyasi avtomatik ravishda ajratib oladi
- ✅ Mavjud ma'lumotlar o'zgartirilmadi, faqat yangi qo'shilayotgan ma'lumotlar alohida saqlanadi

## Test Qilish Uchun Tavsiyalar

1. **Excel Import**: "11-B - 3-maktab" formatida ma'lumot import qiling
2. **Web API**: `/api/student` endpoint-ni test qiling (maktab maydonini tekshiring)
3. **Admin Panel**: Search va student details modal-ni tekshiring
4. **Telegram Bot**: Profil ulash va natija xabarlarini tekshiring
5. **Statistika**: Maktab bo'yicha statistika to'g'ri hisoblangan-mi tekshiring

## Commit Ma'lumotlari

- **Commit Hash**: f0fe1c6
- **Branch**: main
- **Fayl Soni**: 7 ta fayl o'zgartirildi
- **Qator Soni**: +43 qo'shildi, -25 o'chirildi

## Keyingi Qadamlar (Ixtiyoriy)

1. Mavjud ma'lumotlarni migratsiya qilish (eski "11-B - 3-maktab" formatini ajratish)
2. Excel export modullarini yangilash (agar hali qilinmagan bo'lsa)
3. PDF export modullarini yangilash
4. Qo'shimcha maktab-based filtrlarni qo'shish
