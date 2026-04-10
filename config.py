import os

# Bot tokeni Railway environment variable'dan olinadi
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Admin paroli — Railway'da ADMIN_PASSWORD env variable sifatida saqlang
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Ball koeffitsientlari
MAJBURIY_KOEFF = 1.1       # Ona tili + Matematika + Tarix (jami 30 savol)
ASOSIY_1_KOEFF = 3.1       # 1-asosiy fan (30 savol)
ASOSIY_2_KOEFF = 2.1       # 2-asosiy fan (30 savol)

MAX_SAVOL = 30             # Har bir guruhda maksimal savol soni

# Mavjud yo'nalishlar (asosiy fan juftliklari)
YONALISHLAR = [
    "Matematika + Fizika",
    "Matematika + Ingliz tili",
    "Matematika + Kimyo",
    "Matematika + Informatika",
    "Ingliz tili + Ona tili",
    "Ingliz tili + Tarix",
    "Biologiya + Kimyo",
    "Tarix + Geografiya",
    "Boshqa",
]
