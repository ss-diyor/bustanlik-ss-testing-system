from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    SwitchInlineQueryChosenChat
)
from database import yonalish_ol, sinf_ol, kalit_ol, oqituvchilar_hammasi


def admin_menu_keyboard():
    """Admin bosh menyusi — reply keyboard."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ O'quvchi qo'shish")],
            [KeyboardButton(text="📥 Exceldan import")],
            [KeyboardButton(text="🔑 Test kalitlarini boshqarish")],
            [KeyboardButton(text="✏️ Natijani tahrirlash")],
            [KeyboardButton(text="⚙️ Yo'nalishlarni boshqarish")],
            [KeyboardButton(text="🏫 Sinflarni boshqarish")],
            [KeyboardButton(text="👨‍🏫 O'qituvchilarni boshqarish")],
            [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="🏆 Reyting")],
            [KeyboardButton(text="📋 O'quvchilar ro'yxati")],
            [KeyboardButton(text="⏰ Eslatmalar"), KeyboardButton(text="🏫 Maktablarni boshqarish")],
            [KeyboardButton(text="📢 Guruhlarni boshqarish")],
            [KeyboardButton(text="🔔 So'rovlar"), KeyboardButton(text="⚖️ Apellyatsiyalar")],
            [KeyboardButton(text="⚙️ Sozlamalar"), KeyboardButton(text="📥 Excelga yuklash")],
            [KeyboardButton(text="🧹 Bazani tozalash")],
            [KeyboardButton(text="📢 Xabar yuborish")],
            [KeyboardButton(text="🔍 Kod bo'yicha qidirish")],
            [KeyboardButton(text="🚪 Chiqish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
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
        resize_keyboard=True
    )


def yonalish_keyboard():
    """Yo'nalishlarni inline tugmalar sifatida chiqaradi (dinamik)."""
    buttons = []
    yonalishlar = yonalish_ol()
    for y in yonalishlar:
        buttons.append([InlineKeyboardButton(text=y, callback_data=f"yonalish:{y}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_keyboard():
    """Sinflarni inline tugmalar sifatida chiqaradi (dinamik)."""
    buttons = []
    sinflar = sinf_ol()
    for s in sinflar:
        buttons.append([InlineKeyboardButton(text=s, callback_data=f"sinf:{s}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def yonalish_boshqarish_keyboard():
    """Yo'nalishlarni boshqarish menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Mavjud yo'nalishlar", callback_data="yonalish_boshqar:ro'yxat")],
        [InlineKeyboardButton(text="➕ Yangi yo'nalish qo'shish", callback_data="yonalish_boshqar:qosh")],
        [InlineKeyboardButton(text="❌ Yo'nalishni o'chirish", callback_data="yonalish_boshqar:ochir")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="yonalish_boshqar:orqaga")],
    ])


def sinf_boshqarish_keyboard():
    """Sinflarni boshqarish menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Mavjud sinflar", callback_data="sinf_boshqar:ro'yxat")],
        [InlineKeyboardButton(text="➕ Yangi sinf qo'shish", callback_data="sinf_boshqar:qosh")],
        [InlineKeyboardButton(text="❌ Sinfni o'chirish", callback_data="sinf_boshqar:ochir")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="sinf_boshqar:orqaga")],
    ])


def kalit_boshqarish_keyboard():
    """
    Test kalitlarini boshqarish menyusi.
    Umumiy kalit + Yo'nalish bo'yicha kalit qo'shish imkoni.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Mavjud kalitlar", callback_data="kalit_boshqar:ro'yxat")],
        [InlineKeyboardButton(text="➕ Umumiy kalit qo'shish", callback_data="kalit_boshqar:qosh")],
        [InlineKeyboardButton(text="🎯 Yo'nalishga kalit qo'shish", callback_data="kalit_boshqar:yonalish_qosh")],
        [InlineKeyboardButton(text="❌ Mavjud kalitlarni o'chirish", callback_data="kalit_boshqar:ochir")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="kalit_boshqar:orqaga")],
    ])


def kalit_actions_keyboard(test_nomi, holat):
    """Har bir kalit uchun amallar."""
    holat_text = "🔓 Ochish" if holat == "yopiq" else "🔒 Yopish"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"kalit_edit:{test_nomi}")],
        [InlineKeyboardButton(text=holat_text, callback_data=f"kalit_status:{test_nomi}")],
        [InlineKeyboardButton(text="❌ O'chirish", callback_data=f"kalit_del:{test_nomi}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="kalit_boshqar:ro'yxat")],
    ])


def kalit_yonalish_tanlash_keyboard():
    """Kalit uchun yo'nalish tanlash (inline)."""
    buttons = []
    yonalishlar = yonalish_ol()
    for y in yonalishlar:
        # callback_data uzunligi 64 belgidan oshmasligi uchun truncate
        cb_data = f"kalit_yonalish:{y[:40]}"
        buttons.append([InlineKeyboardButton(text=y, callback_data=cb_data)])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="kalit_boshqar:orqaga")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def yonalish_ochirish_keyboard():
    """Yo'nalishlarni o'chirish uchun ro'yxat."""
    buttons = []
    yonalishlar = yonalish_ol()
    for y in yonalishlar:
        buttons.append([InlineKeyboardButton(text=f"❌ {y}", callback_data=f"yonalish_ochir:{y}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="yonalish_boshqar:orqaga")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def sinf_ochirish_keyboard():
    """Sinflarni o'chirish uchun ro'yxat."""
    buttons = []
    sinflar = sinf_ol()
    for s in sinflar:
        buttons.append([InlineKeyboardButton(text=f"❌ {s}", callback_data=f"sinf_ochir:{s}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="sinf_boshqar:orqaga")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def tasdiqlash_keyboard():
    """✅ Saqlash / ❌ Bekor qilish tugmalari."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Saqlash", callback_data="tasdiq:ha"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="tasdiq:yoq"),
        ]
    ])


def baza_tozalash_keyboard():
    """Bazani tozalashni tasdiqlash uchun inline tugmalar."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ HA, tozalansin", callback_data="baza_tozalash:ha"),
            InlineKeyboardButton(text="❌ YO'Q, bekor qilinsin", callback_data="baza_tozalash:yoq"),
        ]
    ])


def user_menu_keyboard(ranking_enabled='True', stats_enabled='True'):
    """Foydalanuvchi asosiy menyusi (Dinamik)."""
    keyboard = []
    
    # Birinchi qator: Mening natijalarim, Shaxsiy kabinet, Mening o'rnim
    row1 = [KeyboardButton(text="📊 Mening natijalarim"), KeyboardButton(text="👤 Shaxsiy kabinet")]
    if ranking_enabled == 'True':
        row1.append(KeyboardButton(text="🏆 Mening o'rnim"))
    keyboard.append(row1)
    
    # Ikkinchi qator: Javoblarni tekshirish, Apellyatsiya yuborish
    keyboard.append([KeyboardButton(text="✅ Javoblarni tekshirish"), KeyboardButton(text="⚖️ Apellyatsiya")])
    
    # Uchinchi qator: Statistika (agar yoqilgan bo'lsa)
    if stats_enabled == 'True':
        keyboard.append([KeyboardButton(text="📈 Statistika")])
    
    # To'rtinchi qator: Admin bilan bog'lanish
    keyboard.append([KeyboardButton(text="✍️ Admin bilan bog'lanish")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True
    )


def test_tanlash_keyboard(yonalish: str = None):
    """
    O'quvchi uchun ochiq testlar ro'yxati.
    Agar yonalish berilsa — faqat o'sha yo'nalish + umumiy (yonalish=NULL) kalitlari ko'rsatiladi.
    """
    buttons = []
    kalitlar = kalit_ol()
    for k in kalitlar:
        if k['holat'] != 'ochiq':
            continue
        # Agar kalit biror yo'nalishga bog'liq bo'lsa va talabaning yo'nalishi mos kelmasa — o'tkazib yuborish
        if k.get('yonalish') and yonalish and k['yonalish'] != yonalish:
            continue
        label = k['test_nomi']
        if k.get('yonalish'):
            label = f"🎯 {k['test_nomi']} ({k['yonalish']})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"check_test:{k['test_nomi']}")])

    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def murojaat_bekor_qilish_keyboard():
    """Murojaatni bekor qilish tugmasi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True
    )


def murojaat_javob_keyboard(user_id):
    """Admin uchun murojaatga javob berish tugmasi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Javob berish", callback_data=f"murojaat_javob:{user_id}")]
    ])

def ranking_keyboard(is_admin=False):
    """Reyting menyusi."""
    if is_admin:
        buttons = [
            [InlineKeyboardButton(text="🏫 Tanlangan sinf reytingi", callback_data="ranking:select_class")],
            [InlineKeyboardButton(text="📊 Sinflar bo'yicha Top", callback_data="ranking:top_by_classes")],
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text="🌍 Umumiy Top 50", callback_data="ranking:overall_top50")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="ranking:back")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def sinf_tanlash_ranking_keyboard():
    """Admin uchun reyting ko'rishda sinf tanlash."""
    buttons = []
    sinflar = sinf_ol()
    for s in sinflar:
        buttons.append([InlineKeyboardButton(text=s, callback_data=f"ranking:view_class:{s}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="ranking:back_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def sinf_prefix_tanlash_keyboard():
    """Admin uchun sinf prefikslarini (9, 10, 11) tanlash."""
    buttons = []
    sinflar = sinf_ol()
    import re
    prefixes = sorted(list(set([re.match(r'(\d+)', s).group(1) for s in sinflar if re.match(r'(\d+)', s)])))
    
    for p in prefixes:
        buttons.append([InlineKeyboardButton(text=f"{p}-sinflar", callback_data=f"ranking:top_prefix:{p}")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="ranking:back_admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def stats_keyboard():
    """Statistika menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎯 Yo'nalishlar bo'yicha", callback_data="stats:direction")],
        [InlineKeyboardButton(text="🏫 Sinflar bo'yicha", callback_data="stats:class")],
        [InlineKeyboardButton(text="🚀 Eng ko'p o'sganlar", callback_data="stats:improved")],
    ])

def oquvchilar_filtrlash_keyboard():
    """O'quvchilar ro'yxatini filtrlash menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏫 Sinf bo'yicha", callback_data="filter_type:sinf")],
        [InlineKeyboardButton(text="🎯 Yo'nalish bo'yicha", callback_data="filter_type:yonalish")],
        [InlineKeyboardButton(text="📋 Hammasi", callback_data="filter_type:hammasi")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="filter_type:orqaga")],
    ])

def sinf_tanlash_keyboard(action_prefix="filter_sinf"):
    """Sinf tanlash uchun inline tugmalar."""
    buttons = []
    sinflar = sinf_ol()
    for s in sinflar:
        if action_prefix == "filter_sinf":
            buttons.append([InlineKeyboardButton(text=s, callback_data=f"filter_val:sinf:{s}")])
        else:
            buttons.append([InlineKeyboardButton(text=s, callback_data=f"{action_prefix}:{s}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="filter_type:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def yonalish_tanlash_keyboard(action_prefix="filter_yon"):
    """Yo'nalish tanlash uchun inline tugmalar."""
    buttons = []
    yonalishlar = yonalish_ol()
    for y in yonalishlar:
        if action_prefix == "filter_yon":
            buttons.append([InlineKeyboardButton(text=y, callback_data=f"filter_val:yonalish:{y[:40]}")])
        else:
            buttons.append([InlineKeyboardButton(text=y, callback_data=f"{action_prefix}:{y[:40]}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="filter_type:back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def filter_actions_keyboard(filter_type="all", filter_value="all"):
    """Filtrlangan ro'yxat uchun amallar (Excel yuklash)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Excelga yuklash", callback_data=f"filter_excel:{filter_type}:{filter_value}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="filter_type:back")],
    ])

def settings_keyboard(ranking_enabled, stats_enabled):
    """Bot sozlamalari klaviaturasi."""
    ranking_text = "✅ Reyting Yoqilgan" if ranking_enabled == 'True' else "❌ Reyting O'chirilgan"
    stats_text = "✅ Statistika Yoqilgan" if stats_enabled == 'True' else "❌ Statistika O'chirilgan"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ranking_text, callback_data="toggle_setting:ranking_enabled")],
        [InlineKeyboardButton(text=stats_text, callback_data="toggle_setting:stats_enabled")],
    ])

def request_actions_keyboard(request_id, user_id=None):
    """So'rovlar uchun amallar."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ 5 daqiqa", callback_data=f"request_action:approve_5m:{request_id}"),
            InlineKeyboardButton(text="✅ 30 daqiqa", callback_data=f"request_action:approve_30m:{request_id}"),
        ],
        [
            InlineKeyboardButton(text="✅ 1 soat", callback_data=f"request_action:approve_1h:{request_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"request_action:reject:{request_id}")
        ]
    ]
    if user_id:
        buttons.append([InlineKeyboardButton(text="🚫 Ruxsatni qaytarib olish", callback_data=f"request_action:revoke:{user_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def profile_keyboard():
    """Shaxsiy kabinet uchun inline tugmalar."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Testlar tarixi", callback_data="profile:history")],
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="profile:refresh")],
        [InlineKeyboardButton(text="📤 Natijani ulashish", switch_inline_query_chosen_chat=SwitchInlineQueryChosenChat(query="my_result", allow_user_chats=True, allow_group_chats=True, allow_channel_chats=False))]
    ])

def oqituvchi_boshqarish_keyboard():
    """O'qituvchilarni boshqarish menyusi."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 O'qituvchilar ro'yxati", callback_data="oqituvchi_boshqar:ro'yxat")],
        [InlineKeyboardButton(text="➕ Yangi o'qituvchi qo'shish", callback_data="oqituvchi_boshqar:qosh")],
        [InlineKeyboardButton(text="❌ O'qituvchini o'chirish", callback_data="oqituvchi_boshqar:ochir")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="oqituvchi_boshqar:orqaga")],
    ])

def oqituvchi_ochirish_keyboard():
    """O'qituvchilarni o'chirish uchun ro'yxat."""
    buttons = []
    oqituvchilar = oqituvchilar_hammasi()
    for o in oqituvchilar:
        buttons.append([InlineKeyboardButton(text=f"❌ {o['ismlar']} ({o['sinf']})", callback_data=f"oqituvchi_ochir:{o['user_id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="oqituvchi_boshqar:orqaga")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def reminder_boshqarish_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi eslatma qo'shish", callback_data="reminder:qosh")],
        [InlineKeyboardButton(text="📋 Kutilayotgan eslatmalar", callback_data="reminder:ro'yxat")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu")],
    ])

def reminder_list_keyboard(reminders):
    buttons = []
    for r in reminders:
        buttons.append([InlineKeyboardButton(text=f"❌ {r['xabar'][:20]}...", callback_data=f"reminder_del:{r['id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="reminder:orqaga")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def maktab_boshqarish_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi maktab qo'shish", callback_data="maktab:qosh")],
        [InlineKeyboardButton(text="📋 Maktablar ro'yxati", callback_data="maktab:ro'yxat")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu")],
    ])

def maktab_list_keyboard(maktablar):
    buttons = []
    for m in maktablar:
        buttons.append([InlineKeyboardButton(text=f"🏫 {m['nomi']}", callback_data=f"maktab_view:{m['id']}")])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="maktab:orqaga")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def maktab_detail_keyboard(maktab_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Sinfni maktabga bog'lash", callback_data=f"maktab_sinf_add:{maktab_id}")],
        [InlineKeyboardButton(text="❌ Maktabni o'chirish", callback_data=f"maktab_del:{maktab_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="maktab:ro'yxat")],
    ])

def guruh_boshqarish_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Guruhlar ro'yxati", callback_data="guruh:ro'yxat")],
        [InlineKeyboardButton(text="📊 Guruhda reyting e'lon qilish", callback_data="guruh:ranking")],
        [InlineKeyboardButton(text="💾 Guruhga Backup yuborish", callback_data="guruh:backup")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_menu")],
    ])

def appeals_keyboard(appeals_list):
    """Apellyatsiyalar ro'yxati uchun inline tugmalar."""
    buttons = []
    for a in appeals_list:
        buttons.append([InlineKeyboardButton(text=f"⚖️ {a['ismlar']} ({a['talaba_kod']})", callback_data=f"appeal_view:{a['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def appeal_action_keyboard(appeal_id):
    """Bitta apellyatsiya uchun amallar."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Javob berish", callback_data=f"appeal_reply:{appeal_id}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="appeal_list")]
    ])
