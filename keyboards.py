from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    SwitchInlineQueryChosenChat,
    WebAppInfo,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from database import (
    yonalish_ol,
    sinf_ol,
    sinf_ol_batafsil,
    kalit_ol,
    oqituvchilar_hammasi,
)


def admin_menu_keyboard():
    """Admin bosh menyusi — reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ O'quvchi qo'shish")],
            [KeyboardButton(text="🔢 Kod generatori")],
            [KeyboardButton(text="📥 Exceldan import")],
            [
                KeyboardButton(text="📝 Mock natija qo'shish"),
                KeyboardButton(text="📊 Mock natijalarini ko'rish"),
            ],
            [
                KeyboardButton(text="📥 Excel import"),
                KeyboardButton(text="📄 Shablon yuklab olish"),
            ],
            [KeyboardButton(text="⚙️ Mock fanlar boshqaruvi")],
            [KeyboardButton(text="✏️ O'quvchi ma'lumotlarini tahrirlash")],
            [KeyboardButton(text="🗑️ Bitta natijani o'chirish")],
            [KeyboardButton(text="🔑 Test kalitlarini boshqarish")],
            [KeyboardButton(text="✏️ Natijani tahrirlash")],
            [KeyboardButton(text="⚙️ Yo'nalishlarni boshqarish")],
            [KeyboardButton(text="🏫 Sinflarni boshqarish")],
            [KeyboardButton(text="🔄 Sinf transferi")],
            [KeyboardButton(text="📦 Bitiruvchilarni arxivlash")],
            [KeyboardButton(text="🔍 Dublikatlarni topish")],
            [KeyboardButton(text="👨‍🏫 O'qituvchilarni boshqarish")],
            [KeyboardButton(text="👥 Adminlarni boshqarish")],
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="🏫 Maktab statistikasi"),
            ],
            [
                KeyboardButton(text="🏆 Reyting"),
                KeyboardButton(text="📄 PDF Hisobot"),
            ],
            [KeyboardButton(text="📊 Excel Hisobot")],
            [KeyboardButton(text="📗 Google Sheets Eksport")],
            [
                KeyboardButton(text="⚖️ Sinf taqqoslash"),
                KeyboardButton(text="📋 O'quvchilar ro'yxati"),
            ],
            [KeyboardButton(text="📱 Ro'yxatdan o'tganlar")],
            [
                KeyboardButton(text="⏰ Eslatmalar"),
                KeyboardButton(text="🏫 Maktablarni boshqarish"),
            ],
            [KeyboardButton(text="📢 Guruhlarni boshqarish")],
            [
                KeyboardButton(text="🔔 So'rovlar"),
                KeyboardButton(text="⚖️ Apellyatsiyalar"),
            ],
            [
                KeyboardButton(text="⚙️ Sozlamalar"),
                KeyboardButton(text="📥 Excelga yuklash"),
            ],
            [KeyboardButton(text="🤖 Chatbot foydalanuvchilar")],
            [KeyboardButton(text="🏆 Reyting Excel")],
            [KeyboardButton(text="🧹 Bazani tozalash")],
            [KeyboardButton(text="📢 Xabar yuborish")],
            [KeyboardButton(text="📧 Email xabar yuborish")],
            [KeyboardButton(text="✉️ Shaxsiy xabar yuborish")],
            [KeyboardButton(text="🌐 Web Admin Panel")],
            [KeyboardButton(text="📦 Mini-test yuborish")],
            [KeyboardButton(text="📝 Mashq Quiz (Web)")],
            [KeyboardButton(text="🔍 Kod bo'yicha qidirish")],
            [KeyboardButton(text="🎭 Demo kodlar")],
            [KeyboardButton(text="🚪 Chiqish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def admin_inline_menu():
    """Admin uchun inline tugmalar (Web App bilan)."""
    from config import WEBAPP_URL
    if not WEBAPP_URL:
        return None
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Admin Web Panel", web_app=WebAppInfo(url=f"{WEBAPP_URL}/admin"))]
        ]
    )


def oqituvchi_menu_keyboard():
    """O'qituvchi (cheklangan admin) menyusi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Mening sinfim statistikasi")],
            [KeyboardButton(text="🏆 Mening sinfim reytingi")],
            [KeyboardButton(text="📋 Sinfim o'quvchilari")],
            [KeyboardButton(text="📥 Sinfim natijalari (Excel)")],
            [KeyboardButton(text="🚪 Chiqish")],
        ],
        resize_keyboard=True,
    )


def yonalish_keyboard(prefix="yonalish_idx"):
    """Yo'nalishlarni inline tugmalar sifatida chiqaradi (dinamik, safe callback)."""
    buttons = []
    yonalishlar = yonalish_ol()
    for idx, y in enumerate(yonalishlar):
        buttons.append(
            [InlineKeyboardButton(text=y, callback_data=f"{prefix}:{idx}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


SINF_PAGE_SIZE = 8  # Bir sahifada nechta sinf ko'rsatiladi


def _build_sinf_page_buttons(
    sinflar: list,
    page: int,
    page_callback: str,
    sinf_callback_prefix: str,
    back_callback: str,
) -> InlineKeyboardMarkup:
    """
    Umumiy pagination klaviatura quruvchi.
    sinflar        — sinf_ol_batafsil() natijasi
    page           — joriy sahifa (0 dan boshlanadi)
    page_callback  — sahifa almashtirish uchun prefix (masalan: 'sinf_page')
    sinf_callback_prefix — sinf bosilganda prefix (masalan: 'sinf_id')
    back_callback  — Orqaga tugmasi callback
    """
    total = len(sinflar)
    total_pages = max(1, (total + SINF_PAGE_SIZE - 1) // SINF_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start = page * SINF_PAGE_SIZE
    end = start + SINF_PAGE_SIZE
    sahifadagi_sinflar = sinflar[start:end]

    buttons = []

    # Maktab sarlavhasi + sinf tugmalari
    joriy_maktab = None
    for s in sahifadagi_sinflar:
        if s["maktab_nomi"] != joriy_maktab:
            joriy_maktab = s["maktab_nomi"]
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"🏫 {joriy_maktab}", callback_data="no_action"
                    )
                ]
            )
        label = s.get("button_text", f"  📚 {s['nomi']}")
        buttons.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"{sinf_callback_prefix}:{s['id']}",
                )
            ]
        )

    # Navigatsiya qatori
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(
                InlineKeyboardButton(
                    text="◀️ Oldingi",
                    callback_data=f"{page_callback}:{page - 1}",
                )
            )
        nav.append(
            InlineKeyboardButton(
                text=f"📄 {page + 1}/{total_pages}", callback_data="no_action"
            )
        )
        if page < total_pages - 1:
            nav.append(
                InlineKeyboardButton(
                    text="Keyingi ▶️",
                    callback_data=f"{page_callback}:{page + 1}",
                )
            )
        buttons.append(nav)

    buttons.append(
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_callback)]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    """
    Sinf tanlash klaviaturasi (sahifalangan).
    callback_data: sinf_id:{id}
    Sahifa navigatsiyasi: sinf_page:{page}
    """
    sinflar = sinf_ol_batafsil()
    if not sinflar:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⚠️ Sinflar yo'q", callback_data="no_action"
                    )
                ]
            ]
        )
    for s in sinflar:
        s["button_text"] = f"  📚 {s['nomi']}"
    return _build_sinf_page_buttons(
        sinflar=sinflar,
        page=page,
        page_callback="sinf_page",
        sinf_callback_prefix="sinf_id",
        back_callback="cancel:admin_menu",
    )


def yonalish_boshqarish_keyboard():
    """Yo'nalishlarni boshqarish menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Mavjud yo'nalishlar",
                    callback_data="yonalish_boshqar:ro'yxat",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Yangi yo'nalish qo'shish",
                    callback_data="yonalish_boshqar:qosh",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Yo'nalishni o'chirish",
                    callback_data="yonalish_boshqar:ochir",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish", callback_data="cancel:admin_menu"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="yonalish_boshqar:orqaga"
                )
            ],
        ]
    )


def sinf_boshqarish_keyboard():
    """Sinflarni boshqarish menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Mavjud sinflar",
                    callback_data="sinf_boshqar:ro'yxat",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Yangi sinf qo'shish",
                    callback_data="sinf_boshqar:qosh",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Sinfni o'chirish",
                    callback_data="sinf_boshqar:ochir",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="sinf_boshqar:orqaga"
                )
            ],
        ]
    )


def kalit_boshqarish_keyboard():
    """
    Test kalitlarini boshqarish menyusi.
    Umumiy kalit + Yo'nalish bo'yicha kalit qo'shish imkoni.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Mavjud kalitlar",
                    callback_data="kalit_boshqar:ro'yxat",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Umumiy kalit qo'shish",
                    callback_data="kalit_boshqar:qosh",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Yo'nalishga kalit qo'shish",
                    callback_data="kalit_boshqar:yonalish_qosh",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Mavjud kalitlarni o'chirish",
                    callback_data="kalit_boshqar:ochir",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="kalit_boshqar:orqaga"
                )
            ],
        ]
    )


def kalit_actions_keyboard(test_nomi, holat):
    """Har bir kalit uchun amallar."""
    holat_text = "🔓 Ochish" if holat == "yopiq" else "🔒 Yopish"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Tahrirlash",
                    callback_data=f"kalit_edit:{test_nomi}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=holat_text, callback_data=f"kalit_status:{test_nomi}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ O'chirish", callback_data=f"kalit_del:{test_nomi}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="kalit_boshqar:ro'yxat"
                )
            ],
        ]
    )


def kalit_yonalish_tanlash_keyboard():
    """Kalit uchun yo'nalish tanlash (inline)."""
    buttons = []
    yonalishlar = yonalish_ol()
    for y in yonalishlar:
        # callback_data uzunligi 64 belgidan oshmasligi uchun truncate
        cb_data = f"kalit_yonalish:{y[:40]}"
        buttons.append([InlineKeyboardButton(text=y, callback_data=cb_data)])
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="kalit_boshqar:orqaga"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def yonalish_ochirish_keyboard():
    """Yo'nalishlarni o'chirish uchun ro'yxat."""
    buttons = []
    yonalishlar = yonalish_ol()
    for y in yonalishlar:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"❌ {y}", callback_data=f"yonalish_ochir:{y}"
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="yonalish_boshqar:orqaga"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_ochirish_keyboard(page: int = 0) -> InlineKeyboardMarkup:
    """
    Sinflarni o'chirish klaviaturasi (sahifalangan).
    callback_data: sinf_ochir_id:{id}
    Sahifa navigatsiyasi: sinf_ochir_page:{page}
    """
    sinflar = sinf_ol_batafsil()
    if not sinflar:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⚠️ Sinflar yo'q", callback_data="no_action"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Orqaga", callback_data="sinf_boshqar:orqaga"
                    )
                ],
            ]
        )
    for s in sinflar:
        s["button_text"] = f"❌ {s['nomi']}"
    return _build_sinf_page_buttons(
        sinflar=sinflar,
        page=page,
        page_callback="sinf_ochir_page",
        sinf_callback_prefix="sinf_ochir_id",
        back_callback="sinf_boshqar:orqaga",
    )


def tasdiqlash_keyboard():
    """✅ Saqlash / ❌ Bekor qilish tugmalari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Saqlash", callback_data="tasdiq:ha"
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish", callback_data="tasdiq:yoq"
                ),
            ]
        ]
    )


def broadcast_cancel_keyboard():
    """Xabar yuborishni bekor qilish uchun vaqtinchalik keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Xabar yuborishni bekor qilish")]],
        resize_keyboard=True,
    )


def broadcast_confirm_keyboard():
    """Xabar yuborishni tasdiqlash/rad etish tugmalari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Jo'natish", callback_data="broadcast:confirm"
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish", callback_data="broadcast:cancel"
                ),
            ]
        ]
    )


def broadcast_target_keyboard():
    """Broadcast maqsadini tanlash: barcha, maktab, sinf yoki yo'nalish bo'yicha."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 Barcha foydalanuvchilar",
                    callback_data="bcast_target:all"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏫 Maktab bo'yicha",
                    callback_data="bcast_target:school"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎓 Sinf bo'yicha",
                    callback_data="bcast_target:sinf"
                ),
                InlineKeyboardButton(
                    text="📚 Yo'nalish bo'yicha",
                    callback_data="bcast_target:yonalish"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="bcast_target:cancel"
                )
            ],
        ]
    )


def broadcast_maktab_tanlash_keyboard(maktablar: list):
    """Broadcast uchun maktablar ro'yxatidan birini tanlash uchun inline keyboard."""
    buttons = []
    for m in maktablar:
        buttons.append([
            InlineKeyboardButton(
                text=f"🏫 {m['nomi']}",
                callback_data=f"bcast_school:{m['id']}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="bcast_school:cancel"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def broadcast_sinf_tanlash_keyboard(sinflar: list):
    """Broadcast uchun sinflar ro'yxatidan birini tanlash uchun inline keyboard."""
    buttons = []
    for sinf_nomi in sinflar:
        buttons.append([
            InlineKeyboardButton(
                text=f"🎓 {sinf_nomi}",
                callback_data=f"bcast_sinf:{sinf_nomi}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="bcast_sinf:cancel"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def broadcast_yonalish_tanlash_keyboard(yonalishlar: list):
    """Broadcast uchun yo'nalishlar ro'yxatidan birini tanlash uchun inline keyboard."""
    buttons = []
    for y in yonalishlar:
        buttons.append([
            InlineKeyboardButton(
                text=f"📚 {y}",
                callback_data=f"bcast_yonalish:{y}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="bcast_yonalish:cancel"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shaxsiy_xabar_confirm_keyboard(user_id: int):
    """Shaxsiy xabarni tasdiqlash tugmalari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Yuborish",
                    callback_data=f"pmsend:confirm:{user_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="pmsend:cancel"
                ),
            ]
        ]
    )


def baza_tozalash_keyboard():
    """Bazani tozalashni tasdiqlash uchun inline tugmalar."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ HA, tozalansin", callback_data="baza_tozalash:ha"
                ),
                InlineKeyboardButton(
                    text="❌ YO'Q, bekor qilinsin",
                    callback_data="baza_tozalash:yoq",
                ),
            ]
        ]
    )


def user_menu_keyboard(
    ranking_enabled="True",
    stats_enabled="True",
    chatbot_enabled="True",
    mock_enabled="True",
    quiz_enabled="True",
    mini_test_enabled="True",
):
    """Foydalanuvchi asosiy menyusi (Dinamik)."""
    keyboard = []

    # Birinchi qator: Mening natijam, Shaxsiy kabinet, Mening o'rnim
    row1 = [
        KeyboardButton(text="📊 Mening natijam"),
        KeyboardButton(text="👤 Shaxsiy kabinet"),
    ]
    if ranking_enabled == "True":
        row1.append(KeyboardButton(text="🏆 Mening o'rnim"))
    keyboard.append(row1)

    # Ikkinchi qator: Javoblarni tekshirish, Apellyatsiya yuborish
    keyboard.append(
        [
            KeyboardButton(text="✅ Javoblarni tekshirish"),
            KeyboardButton(text="⚖️ Apellyatsiya"),
        ]
    )

    # Mock natijalar tugmasi (admin sozlamalari orqali yoqib/o'chiriladi)
    if mock_enabled == "True":
        keyboard.append([KeyboardButton(text="🧪 Mock natijalarim")])

    # Uchinchi qator: Statistika va AI Analitika
    row3 = []
    if stats_enabled == "True":
        row3.append(KeyboardButton(text="📈 Statistika"))
    row3.append(KeyboardButton(text="🧠 AI Tahlili"))
    if chatbot_enabled == "True":
        row3.append(KeyboardButton(text="🤖 AI Chatbot"))
    keyboard.append(row3)

    # To'rtinchi qator: Mashq qilish va Bildirishnomalar (quiz_enabled bo'lsa)
    row4 = []
    if quiz_enabled == "True":
        row4.append(KeyboardButton(text="📝 Mashq qilish (Quiz)"))
    row4.append(KeyboardButton(text="🔔 Bildirishnomalar"))
    keyboard.append(row4)

    # Mini-testlar (mini_test_enabled bo'lsa, alohida qatorda)
    if mini_test_enabled == "True":
        keyboard.append([KeyboardButton(text="📦 Mini-testlar")])

    # Admin bilan bog'lanish — alohida, to'liq qatorda
    keyboard.append([KeyboardButton(text="✍️ Admin bilan bog'lanish")])

    # Oxirgi qator: Chiqish
    keyboard.append([KeyboardButton(text="🚪 Chiqish")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def phone_number_keyboard():
    """Telefon raqamini yuborish tugmasi"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📱 Raqamimni yuborish", request_contact=True)
    )
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)


def test_tanlash_keyboard(yonalish: str = None):
    """
    O'quvchi uchun ochiq testlar ro'yxati.
    Agar yonalish berilsa — faqat o'sha yo'nalish + umumiy (yonalish=NULL) kalitlari ko'rsatiladi.
    """
    buttons = []
    kalitlar = kalit_ol()
    for k in kalitlar:
        if k["holat"] != "ochiq":
            continue
        # Agar kalit biror yo'nalishga bog'liq bo'lsa va talabaning yo'nalishi mos kelmasa — o'tkazib yuborish
        if k.get("yonalish") and yonalish and k["yonalish"] != yonalish:
            continue
        label = k["test_nomi"]
        if k.get("yonalish"):
            label = f"🎯 {k['test_nomi']} ({k['yonalish']})"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=label, callback_data=f"check_test:{k['test_nomi']}"
                )
            ]
        )

    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def murojaat_bekor_qilish_keyboard():
    """Murojaatni bekor qilish tugmasi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )


def murojaat_javob_keyboard(user_id):
    """Admin uchun murojaatga javob berish tugmasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Javob berish",
                    callback_data=f"murojaat_javob:{user_id}",
                )
            ]
        ]
    )


def notification_settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    def label(enabled: bool) -> str:
        return "✅ Yoqilgan" if enabled else "❌ O'chirilgan"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📊 Natijalar: {label(settings.get('notify_results', True))}",
                    callback_data="notif:toggle:notify_results",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🧪 Mock natijalar: {label(settings.get('notify_mock_results', True))}",
                    callback_data="notif:toggle:notify_mock_results",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"📢 Admin xabarlari: {label(settings.get('notify_admin_messages', True))}",
                    callback_data="notif:toggle:notify_admin_messages",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"⏰ Eslatmalar: {label(settings.get('notify_reminders', True))}",
                    callback_data="notif:toggle:notify_reminders",
                )
            ],
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data="notif:refresh")],
        ]
    )


# ─────────────────────────────────────────
# Yangi funktsiyalar uchun klaviaturalar
# ─────────────────────────────────────────


def talaba_tahrirlash_keyboard(talabalar, page=1, per_page=15):
    """O'quvchini tahrirlash uchun ro'yxat (pagination)."""
    buttons = []
    total = len(talabalar)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start = (page - 1) * per_page
    end = start + per_page

    for talaba in talabalar[start:end]:
        text = f"{talaba['ismlar']} ({talaba['sinf']}) - {talaba['kod']}"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=text, callback_data=f"talaba_edit:{talaba['kod']}"
                )
            ]
        )

    if total_pages > 1:
        nav = []
        if page > 1:
            nav.append(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"talaba_edit_page:{page-1}"
                )
            )
        nav.append(
            InlineKeyboardButton(
                text=f"{page}/{total_pages}",
                callback_data="talaba_edit_page:noop",
            )
        )
        if page < total_pages:
            nav.append(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"talaba_edit_page:{page+1}"
                )
            )
        buttons.append(nav)

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="cancel:admin_menu"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def talaba_edit_options_keyboard(kod):
    """O'quvchini tahrirlash variantlari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Ismni o'zgartirish",
                    callback_data=f"talaba_edit_ism:{kod}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏫 Sinfni o'zgartirish",
                    callback_data=f"talaba_edit_sinf:{kod}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Yo'nalishni o'zgartirish",
                    callback_data=f"talaba_edit_yonalish:{kod}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="talaba_tahrirlash:back"
                )
            ],
        ]
    )


def maktab_statistikasi_keyboard():
    """Maktab statistikasi menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Barcha maktablar statistikasi",
                    callback_data="maktab_stat:barchasi",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📈 Maktablarni solishtirish",
                    callback_data="maktab_stat:solishtirish",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="cancel:admin_menu"
                )
            ],
        ]
    )


def maktablar_tanlash_keyboard():
    """Maktabni tanlash uchun ro'yxat."""
    from database import maktablar_ol

    maktablar = maktablar_ol()
    buttons = []
    for maktab in maktablar:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=maktab["nomi"],
                    callback_data=f"maktab_stat:{maktab['id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="maktab_stat:barchasi"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def maktab_solishtirish_keyboard():
    """Maktablar solishtirish uchun tanlash."""
    from database import maktablar_ol

    maktablar = maktablar_ol()
    buttons = []
    # Birinchi maktabni tanlash
    for i, maktab in enumerate(maktablar):
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"1️⃣ {maktab['nomi']}",
                    callback_data=f"maktab_comp1:{maktab['id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="cancel:admin_menu"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def maktab_comp2_keyboard(maktab1_id):
    """Ikkinchi maktabni tanlash uchun."""
    from database import maktablar_ol

    maktablar = maktablar_ol()
    buttons = []
    for maktab in maktablar:
        if maktab["id"] != maktab1_id:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=f"2️⃣ {maktab['nomi']}",
                        callback_data=f"maktab_comp2:{maktab1_id}:{maktab['id']}",
                    )
                ]
            )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="maktab_stat:solishtirish"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def natijalar_ochirish_keyboard(talaba_kod):
    """O'quvchining natijalarini o'chirish uchun ro'yxat."""
    from database import talaba_natijalari

    natijalar = talaba_natijalari(talaba_kod)
    buttons = []
    for natija in natijalar:
        sana = natija["test_sanasi"].strftime("%d.%m.%Y %H:%M")
        text = f"📊 {natija['umumiy_ball']} ball - {sana}"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"natija_ochir:{talaba_kod}:{natija['id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="cancel:admin_menu"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_transferi_keyboard():
    """Sinf transferi menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Barcha sinflarni yuqoriga ko'chirish",
                    callback_data="sinf_transfer:barchasi",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Tanlab sinfni ko'chirish",
                    callback_data="sinf_transfer:tanlash",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="cancel:admin_menu"
                )
            ],
        ]
    )


def sinf_tanlash_transfer_keyboard():
    """Transfer uchun sinf tanlash — callback_data da ID ishlatiladi (64 bayt limit)."""
    from database import sinf_ol_batafsil

    sinflar = sinf_ol_batafsil()
    buttons = []
    for sinf in sinflar:
        label = f"{sinf['nomi']} - {sinf['maktab_nomi']}"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=label,
                    callback_data=f"sinf_transfer_eski:{sinf['id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="sinf_transfer:menu"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def yangi_sinf_tanlash_keyboard(eski_sinf_id):
    """Yangi sinfni tanlash — callback_data da ID ishlatiladi (64 bayt limit)."""
    from database import sinf_ol_batafsil

    sinflar = sinf_ol_batafsil()
    buttons = []
    for sinf in sinflar:
        if str(sinf["id"]) != str(eski_sinf_id):
            label = f"{sinf['nomi']} - {sinf['maktab_nomi']}"
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=label,
                        callback_data=f"sinf_transfer_yangi:{eski_sinf_id}:{sinf['id']}",
                    )
                ]
            )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="sinf_transfer:tanlash"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def bitiruvchilar_arxivlash_keyboard():
    """Bitiruvchilarni arxivlash menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎓 Barcha 11-sinflarni arxivlash",
                    callback_data="arxivlash:barcha_11",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Tanlab sinfni arxivlash",
                    callback_data="arxivlash:tanlash",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📤 Arxivdan chiqarish",
                    callback_data="arxivlash:chiqarish",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="cancel:admin_menu"
                )
            ],
        ]
    )


def sinf_arxivlash_keyboard():
    """Arxivlash uchun sinf tanlash."""
    from database import sinf_ol

    sinflar = sinf_ol()
    buttons = []
    for sinf in sinflar:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=sinf, callback_data=f"arxivlash_sinf:{sinf}"
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="arxivlash:tanlash"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_arxivdan_chiqarish_keyboard():
    """Arxivdan chiqarish uchun sinf tanlash."""
    from database import sinf_ol

    sinflar = sinf_ol()
    buttons = []
    for sinf in sinflar:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=sinf, callback_data=f"arxivdan_chiqarish_sinf:{sinf}"
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="arxivlash:chiqarish"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def dublikatlar_keyboard(dublikatlar):
    """Dublikat o'quvchilar ro'yxati."""
    buttons = []
    for dublikat in dublikatlar:
        text = f"👥 {dublikat['ismlar']} ({dublikat['soni']} ta)"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=text,
                    callback_data=f"dublikat_tanlash:{dublikat['ismlar']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="cancel:admin_menu"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def dublikat_birlashtirish_keyboard(ism, kodlar):
    """Dublikatlarni birlashtirish uchun."""
    kod_list = kodlar.split(", ")
    buttons = []
    for kod in kod_list:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"👤 {kod}",
                    callback_data=f"dublikat_asosiy:{ism}:{kod}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="dublikatlar:back"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_management_keyboard():
    """Admin boshqarish menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Adminlar ro'yxati",
                    callback_data="admin_manage:list",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Yangi admin qo'shish",
                    callback_data="admin_manage:add",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Adminni o'chirish",
                    callback_data="admin_manage:remove",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="admin_manage:back"
                )
            ],
        ]
    )


def ranking_keyboard(is_admin=False):
    """Reyting menyusi."""
    if is_admin:
        buttons = [
            [
                InlineKeyboardButton(
                    text="🏫 Tanlangan sinf reytingi",
                    callback_data="ranking:select_class",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Sinflar bo'yicha Top",
                    callback_data="ranking:top_by_classes",
                )
            ],
        ]
    else:
        buttons = [
            [
                InlineKeyboardButton(
                    text="🌍 Umumiy Top 50",
                    callback_data="ranking:overall_top50",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="ranking:back"
                )
            ],
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def student_ranking_keyboard():
    """User panel reyting menyusi (student-prefiks)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌍 Umumiy Top 50",
                    callback_data="student_ranking:overall_top50",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="student_ranking:back"
                )
            ],
        ]
    )


def sinf_tanlash_ranking_keyboard():
    """Admin uchun reyting ko'rishda sinf tanlash."""
    buttons = []
    sinflar = sinf_ol()
    for s in sinflar:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=s, callback_data=f"ranking:view_class:{s}"
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="ranking:back_admin"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_prefix_tanlash_keyboard():
    """Admin uchun sinf prefikslarini (9, 10, 11) tanlash."""
    buttons = []
    sinflar = sinf_ol()
    import re

    prefixes = sorted(
        list(
            set(
                [
                    re.match(r"(\d+)", s).group(1)
                    for s in sinflar
                    if re.match(r"(\d+)", s)
                ]
            )
        )
    )

    for p in prefixes:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{p}-sinflar",
                    callback_data=f"ranking:top_prefix:{p}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="ranking:back_admin"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def stats_keyboard():
    """Statistika menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎯 Yo'nalishlar bo'yicha",
                    callback_data="stats:direction",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🥧 Yo'nalishlar pie chart",
                    callback_data="stats:yonalish_pie",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏫 Sinflar bo'yicha", callback_data="stats:class"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚀 Eng ko'p o'sganlar",
                    callback_data="stats:improved",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📉 Eng ko'p pasayganlar",
                    callback_data="stats:declined",
                )
            ],
        ]
    )


def oquvchilar_filtrlash_keyboard():
    """O'quvchilar ro'yxatini filtrlash menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🏫 Sinf bo'yicha", callback_data="filter_type:sinf"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Yo'nalish bo'yicha",
                    callback_data="filter_type:yonalish",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Hammasi", callback_data="filter_type:hammasi"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="filter_type:orqaga"
                )
            ],
        ]
    )


def sinf_tanlash_keyboard(action_prefix="filter_sinf"):
    """Sinf tanlash uchun inline tugmalar."""
    buttons = []
    sinflar = sinf_ol()
    for s in sinflar:
        if action_prefix == "filter_sinf":
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=s, callback_data=f"filter_val:sinf:{s}"
                    )
                ]
            )
        else:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=s, callback_data=f"{action_prefix}:{s}"
                    )
                ]
            )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="filter_type:back"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def yonalish_tanlash_keyboard(action_prefix="filter_yon"):
    """Yo'nalish tanlash uchun inline tugmalar."""
    buttons = []
    yonalishlar = yonalish_ol()
    for y in yonalishlar:
        if action_prefix == "filter_yon":
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=y, callback_data=f"filter_val:yonalish:{y[:40]}"
                    )
                ]
            )
        else:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=y, callback_data=f"{action_prefix}:{y[:40]}"
                    )
                ]
            )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="filter_type:back"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def filter_actions_keyboard(
    filter_type="all", filter_value="all", page=1, total_pages=1
):
    """Filtrlangan ro'yxat uchun amallar (sahifalash + Excel)."""
    rows = []
    if total_pages > 1:
        nav = []
        if page > 1:
            nav.append(
                InlineKeyboardButton(
                    text="⬅️ Oldingi",
                    callback_data=f"filter_page:{filter_type}:{filter_value}:{page-1}",
                )
            )
        if page < total_pages:
            nav.append(
                InlineKeyboardButton(
                    text="Keyingi ➡️",
                    callback_data=f"filter_page:{filter_type}:{filter_value}:{page+1}",
                )
            )
        if nav:
            rows.append(nav)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"📄 {page}/{total_pages}",
                    callback_data="filter_page:noop:noop:1",
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="📥 Excelga yuklash",
                callback_data=f"filter_excel:{filter_type}:{filter_value}",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="🗑 O'quvchini o'chirish",
                callback_data="talaba_ochir_start",
            )
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="filter_type:back"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(
    ranking_enabled,
    stats_enabled,
    chatbot_enabled="True",
    mock_enabled="True",
    quiz_enabled="True",
    mini_test_enabled="True",
):
    """Bot sozlamalari klaviaturasi."""
    ranking_text = (
        "✅ Reyting Yoqilgan"
        if ranking_enabled == "True"
        else "❌ Reyting O'chirilgan"
    )
    stats_text = (
        "✅ Statistika Yoqilgan"
        if stats_enabled == "True"
        else "❌ Statistika O'chirilgan"
    )
    chatbot_text = (
        "✅ AI Chatbot Yoqilgan"
        if chatbot_enabled == "True"
        else "❌ AI Chatbot O'chirilgan"
    )
    mock_text = (
        "✅ Mock natijalar (User): Yoqilgan"
        if mock_enabled == "True"
        else "❌ Mock natijalar (User): O'chirilgan"
    )
    quiz_text = (
        "✅ Mashq qilish (Quiz): Yoqilgan"
        if quiz_enabled == "True"
        else "❌ Mashq qilish (Quiz): O'chirilgan"
    )
    mini_test_text = (
        "✅ Mini-testlar: Yoqilgan"
        if mini_test_enabled == "True"
        else "❌ Mini-testlar: O'chirilgan"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ranking_text,
                    callback_data="toggle_setting:ranking_enabled",
                )
            ],
            [
                InlineKeyboardButton(
                    text=stats_text,
                    callback_data="toggle_setting:stats_enabled",
                )
            ],
            [
                InlineKeyboardButton(
                    text=chatbot_text,
                    callback_data="toggle_setting:chatbot_enabled",
                )
            ],
            [
                InlineKeyboardButton(
                    text=mock_text,
                    callback_data="toggle_setting:mock_enabled",
                )
            ],
            [
                InlineKeyboardButton(
                    text=quiz_text,
                    callback_data="toggle_setting:quiz_enabled",
                )
            ],
            [
                InlineKeyboardButton(
                    text=mini_test_text,
                    callback_data="toggle_setting:mini_test_enabled",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📜 Sertifikat sozlamalari",
                    callback_data="open_cert_sozlama",
                )
            ],
        ]
    )


def request_actions_keyboard(request_id, user_id=None):
    """So'rovlar uchun amallar."""
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ 5 daqiqa",
                callback_data=f"request_action:approve_5m:{request_id}",
            ),
            InlineKeyboardButton(
                text="✅ 30 daqiqa",
                callback_data=f"request_action:approve_30m:{request_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="✅ 1 soat",
                callback_data=f"request_action:approve_1h:{request_id}",
            ),
            InlineKeyboardButton(
                text="❌ Rad etish",
                callback_data=f"request_action:reject:{request_id}",
            ),
        ],
    ]
    if user_id:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🚫 Ruxsatni qaytarib olish",
                    callback_data=f"request_action:revoke:{user_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_keyboard(natija_uslub: str = "kod_bilan"):
    """Shaxsiy kabinet uchun inline tugmalar."""
    from config import WEBAPP_URL

    uslub_text = (
        "⚡ Natija: darhol ko'rsatilsin"
        if natija_uslub == "darhol"
        else "🔐 Natija: kod so'ralsin"
    )
    uslub_cb = (
        "profile:uslub:kod_bilan"
        if natija_uslub == "darhol"
        else "profile:uslub:darhol"
    )

    buttons = [
        [
            InlineKeyboardButton(
                text="📜 Testlar tarixi", callback_data="profile:history"
            )
        ],
        [
            InlineKeyboardButton(
                text="📈 Mening dinamikam", callback_data="profile:chart"
            )
        ],
        [
            InlineKeyboardButton(text=uslub_text, callback_data=uslub_cb)
        ],
        [
            InlineKeyboardButton(
                text="🔄 Yangilash", callback_data="profile:refresh"
            )
        ],
        [
            InlineKeyboardButton(
                text="📤 Natijani ulashish",
                switch_inline_query_chosen_chat=SwitchInlineQueryChosenChat(
                    query="my_result",
                    allow_user_chats=True,
                    allow_group_chats=True,
                    allow_channel_chats=False,
                ),
            )
        ],
    ]

    # Web App tugmasi faqat WEBAPP_URL sozlanganda ko'rinadi
    if WEBAPP_URL:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🌐 Web Panel",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def oqituvchi_boshqarish_keyboard():
    """O'qituvchilarni boshqarish menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 O'qituvchilar ro'yxati",
                    callback_data="oqituvchi_boshqar:ro'yxat",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Yangi o'qituvchi qo'shish",
                    callback_data="oqituvchi_boshqar:qosh",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ O'qituvchini o'chirish",
                    callback_data="oqituvchi_boshqar:ochir",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="oqituvchi_boshqar:orqaga"
                )
            ],
        ]
    )


def oqituvchi_ochirish_keyboard():
    """O'qituvchilarni o'chirish uchun ro'yxat."""
    buttons = []
    oqituvchilar = oqituvchilar_hammasi()
    for o in oqituvchilar:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"❌ {o['ismlar']} ({o['sinf']})",
                    callback_data=f"oqituvchi_ochir:{o['user_id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="oqituvchi_boshqar:orqaga"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def reminder_boshqarish_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Yangi eslatma qo'shish",
                    callback_data="reminder:qosh",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Kutilayotgan eslatmalar",
                    callback_data="reminder:ro'yxat",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="admin_menu"
                )
            ],
        ]
    )


def reminder_list_keyboard(reminders):
    buttons = []
    for r in reminders:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"❌ {r['xabar'][:20]}...",
                    callback_data=f"reminder_del:{r['id']}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🔙 Orqaga", callback_data="reminder:orqaga"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def maktab_boshqarish_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Yangi maktab qo'shish",
                    callback_data="maktab:qosh",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 Maktablar ro'yxati",
                    callback_data="maktab:ro'yxat",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="admin_menu"
                )
            ],
        ]
    )


def maktab_list_keyboard(maktablar):
    buttons = []
    for m in maktablar:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🏫 {m['nomi']}",
                    callback_data=f"maktab_view:{m['id']}",
                )
            ]
        )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="maktab:orqaga")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def maktab_detail_keyboard(maktab_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Sinfni maktabga bog'lash",
                    callback_data=f"maktab_sinf_add:{maktab_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Maktabni o'chirish",
                    callback_data=f"maktab_del:{maktab_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="maktab:ro'yxat"
                )
            ],
        ]
    )


def guruh_boshqarish_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Guruhlar ro'yxati", callback_data="guruh:ro'yxat"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Guruhda reyting e'lon qilish",
                    callback_data="guruh:ranking",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💾 Guruhga Backup yuborish",
                    callback_data="guruh:backup",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Guruhni o'chirish",
                    callback_data="guruh:ochirish_royxat",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="admin_menu"
                )
            ],
        ]
    )


def guruh_ochirish_keyboard(guruhlar: list):
    """Har bir guruh uchun o'chirish tugmasi."""
    buttons = []
    for g in guruhlar:
        nomi = g.get('nomi') or 'Nomsiz guruh'
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {nomi}",
                callback_data=f"guruh_del:{g['chat_id']}",
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="guruh:ro'yxat_menu")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def appeals_keyboard(appeals_list):
    """Apellyatsiyalar ro'yxati uchun inline tugmalar."""
    buttons = []
    for a in appeals_list:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"⚖️ {a['ismlar']} ({a['talaba_kod']})",
                    callback_data=f"appeal_view:{a['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def appeal_action_keyboard(appeal_id):
    """Bitta apellyatsiya uchun amallar."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Javob berish",
                    callback_data=f"appeal_reply:{appeal_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="appeal_list"
                )
            ],
        ]
    )


def maktab_tanlash_keyboard(maktablar, prefix="select_maktab"):
    buttons = []
    for m in maktablar:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f" {m['nomi']}", callback_data=f"{prefix}:{m['id']}"
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text=" Bekor qilish", callback_data="cancel:admin_menu"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def pdf_export_keyboard():
    """PDF export menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=" O'quvchi hisoboti", callback_data="pdf:student"
                )
            ],
            [
                InlineKeyboardButton(
                    text=" Maktab statistikasi",
                    callback_data="pdf:maktab_stat",
                )
            ],
            [
                InlineKeyboardButton(
                    text=" Sinf reytingi", callback_data="pdf:sinf_reyting"
                )
            ],
            [
                InlineKeyboardButton(
                    text=" Orqaga", callback_data="cancel:admin_menu"
                )
            ],
        ]
    )


def sinf_tanlash_pdf_keyboard():
    """PDF uchun sinf tanlash — bitta sinf yoki maktab bo'yicha."""
    from database import sinf_ol

    sinflar = sinf_ol()
    buttons = []
    for sinf in sinflar:
        buttons.append(
            [InlineKeyboardButton(text=sinf, callback_data=f"pdf_sinf:{sinf}")]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🏫 Maktab bo'yicha (barcha sinflar)", callback_data="pdf_sinf_by_maktab"
            )
        ]
    )
    buttons.append(
        [
            InlineKeyboardButton(
                text="📋 Barcha sinflar", callback_data="pdf_sinf:all"
            )
        ]
    )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="pdf:menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_tanlash_pdf_maktab_keyboard(maktab_id: int):
    """Tanlangan maktabdagi sinflarni PDF uchun ko'rsatish."""
    from database import sinf_ol_batafsil

    batafsil = sinf_ol_batafsil()
    maktab_sinflar = [s for s in batafsil if s["maktab_id"] == maktab_id]

    buttons = []
    for s in maktab_sinflar:
        full_name = f"{s['nomi']} - {s['maktab_nomi']}"
        buttons.append(
            [InlineKeyboardButton(text=full_name, callback_data=f"pdf_sinf:{full_name}")]
        )
    # Maktabdagi BARCHA sinflar bir PDF da
    buttons.append(
        [
            InlineKeyboardButton(
                text="📋 Barcha sinflar (shu maktab)",
                callback_data=f"pdf_sinf_maktab:{maktab_id}",
            )
        ]
    )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="pdf:sinf_reyting")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Excel Hisobot keyboardlari ──────────────────────────────────────────────

def excel_export_keyboard():
    """Excel export menyusi — PDF menyusiga parallel."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 O'quvchi hisoboti", callback_data="excel:student"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏫 Maktab statistikasi",
                    callback_data="excel:maktab_stat",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 Sinf reytingi", callback_data="excel:sinf_reyting"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="cancel:admin_menu"
                )
            ],
        ]
    )


def sheets_export_keyboard():
    """Google Sheets eksport menyusi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 O'quvchi tarixi", callback_data="sheets:student"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Barcha o'quvchilar", callback_data="sheets:all_students"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏫 Maktab statistikasi", callback_data="sheets:maktab_stat"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏆 Sinf reytingi", callback_data="sheets:sinf_reyting"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Orqaga", callback_data="cancel:admin_menu"
                )
            ],
        ]
    )


def sinf_tanlash_excel_keyboard():
    """Excel uchun sinf tanlash."""
    from database import sinf_ol

    sinflar = sinf_ol()
    buttons = []
    for sinf in sinflar:
        buttons.append(
            [InlineKeyboardButton(text=sinf, callback_data=f"excel_sinf:{sinf}")]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="🏫 Maktab bo'yicha (barcha sinflar)",
                callback_data="excel_sinf_by_maktab",
            )
        ]
    )
    buttons.append(
        [InlineKeyboardButton(text="📋 Barcha sinflar", callback_data="excel_sinf:all")]
    )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="excel:menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_tanlash_excel_maktab_keyboard(maktab_id: int):
    """Tanlangan maktabdagi sinflarni Excel uchun ko'rsatish."""
    from database import sinf_ol_batafsil

    batafsil = sinf_ol_batafsil()
    maktab_sinflar = [s for s in batafsil if s["maktab_id"] == maktab_id]

    buttons = []
    for s in maktab_sinflar:
        full_name = f"{s['nomi']} - {s['maktab_nomi']}"
        buttons.append(
            [InlineKeyboardButton(text=full_name, callback_data=f"excel_sinf:{full_name}")]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="📋 Barcha sinflar (shu maktab)",
                callback_data=f"excel_sinf_maktab:{maktab_id}",
            )
        ]
    )
    buttons.append(
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="excel:sinf_reyting")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Til tanlash klaviaturalari
def language_selection_keyboard():
    """Til tanlash uchun inline klaviatura"""
    from i18n import i18n
    languages = i18n.get_available_languages()
    
    buttons = []
    for code, name in languages.items():
        buttons.append([InlineKeyboardButton(text=name, callback_data=f"lang:{code}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def language_settings_keyboard():
    """Til sozlamalari klaviaturasi"""
    buttons = [
        [InlineKeyboardButton(text="🌐 Tilni o'zgartirish", callback_data="lang:select")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="menu:main")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── Ota-ona paneli klaviaturalari ────────────────────────────────────────────

def ota_ona_menu_keyboard() -> ReplyKeyboardMarkup:
    """Ota-ona asosiy menyusi — reply keyboard."""
    keyboard = [
        [
            KeyboardButton(text="👨‍👩‍👦 Farzandlarim"),
            KeyboardButton(text="➕ Farzand qo'shish"),
        ],
        [
            KeyboardButton(text="📊 Farzandim natijasi"),
            KeyboardButton(text="🏆 Farzandim reytingi"),
        ],
        [
            KeyboardButton(text="✍️ Admin bilan bog'lanish"),
            KeyboardButton(text="🚪 Chiqish (Ota-ona)"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def farzandlar_tanlash_keyboard(farzandlar: list) -> InlineKeyboardMarkup:
    """
    Bir nechta farzand bo'lganda tanlash uchun inline keyboard.
    Har bir tugma: 'Ism (KOD)' — callback: parent_select:KOD
    """
    from database import talaba_topish
    buttons = []
    for kod in farzandlar:
        talaba = talaba_topish(kod)
        ism = talaba.get("ismlar", kod) if talaba else kod
        sinf = talaba.get("sinf", "") if talaba else ""
        label = f"👤 {ism}"
        if sinf:
            label += f" ({sinf})"
        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"parent_select:{kod}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def farzandlar_boshqarish_keyboard(farzandlar: list) -> InlineKeyboardMarkup:
    """
    Farzandlar ro'yxatini ko'rish va o'chirish uchun inline keyboard.
    Har qatorda: [👤 Ism (KOD)] [❌ O'chirish]
    """
    from database import talaba_topish
    buttons = []
    for kod in farzandlar:
        talaba = talaba_topish(kod)
        ism = talaba.get("ismlar", kod) if talaba else kod
        sinf = talaba.get("sinf", "") if talaba else ""
        label = f"👤 {ism}"
        if sinf:
            label += f" ({sinf})"
        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"parent_view:{kod}"),
            InlineKeyboardButton(text="❌", callback_data=f"parent_del:{kod}"),
        ])
    buttons.append([
        InlineKeyboardButton(text="➕ Yangi farzand qo'shish", callback_data="parent_add_inline"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def farzand_natija_keyboard(kod: str) -> InlineKeyboardMarkup:
    """Farzand natijasini ko'rish sahifasidagi tugmalar."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Barcha natijalar", callback_data=f"parent_all_results:{kod}")],
        [InlineKeyboardButton(text="🏆 Reytingdagi o'rni", callback_data=f"parent_rank:{kod}")],
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="parent_back_list")],
    ])


# ─── Sinf Taqqoslash Keyboardlari ────────────────────────────────────────────

def sinf_taqqoslash_birinchi_keyboard() -> InlineKeyboardMarkup:
    """1-sinf tanlash uchun keyboard."""
    from database import sinf_ol
    sinflar = sinf_ol()
    buttons = []
    for s in sinflar:
        buttons.append([InlineKeyboardButton(
            text=s, callback_data=f"taqq_a:{s}"
        )])
    buttons.append([InlineKeyboardButton(text="❌ Bekor", callback_data="taqq_bekor")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_taqqoslash_ikkinchi_keyboard(sinf_a: str) -> InlineKeyboardMarkup:
    """2-sinf tanlash uchun keyboard (1-sinf tanlangan)."""
    from database import sinf_ol
    sinflar = sinf_ol()
    buttons = []
    for s in sinflar:
        if s != sinf_a:
            buttons.append([InlineKeyboardButton(
                text=s, callback_data=f"taqq_b:{s}"
            )])
    buttons.append([InlineKeyboardButton(
        text="🔙 Orqaga", callback_data="taqq_qayta"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_taqqoslash_natija_keyboard(sinf_a: str, sinf_b: str) -> InlineKeyboardMarkup:
    """Taqqoslash natijasidagi tugmalar."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Excel eksport",
            callback_data=f"taqq_excel:{sinf_a}|{sinf_b}"
        )],
        [InlineKeyboardButton(
            text="🔄 Boshqa sinflarni tanlash",
            callback_data="taqq_qayta"
        )],
        [InlineKeyboardButton(text="❌ Yopish", callback_data="taqq_bekor")],
    ])
