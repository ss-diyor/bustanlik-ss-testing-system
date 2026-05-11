import os


def _env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and (value is None or value.strip() == ""):
        raise RuntimeError(f"{name} environment variable is required")
    return (value or "").strip()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _parse_admin_ids(raw_value: str) -> list[int]:
    ids = []
    for item in raw_value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            ids.append(int(item))
        except ValueError as exc:
            raise RuntimeError(
                "ADMIN_IDS must contain comma-separated integer values"
            ) from exc
    if not ids:
        raise RuntimeError("ADMIN_IDS environment variable is required")
    return ids


# Bot tokeni Railway environment variable'dan olinadi
BOT_TOKEN = _env("BOT_TOKEN", required=True)

# Bot username — verify sahifasida ko'rsatiladi (@ belgisisiz)
BOT_USERNAME = _env("BOT_USERNAME", "bustanlik_ss_bot")

# Admin paroli — Railway'da ADMIN_PASSWORD env variable sifatida saqlang
ADMIN_PASSWORD = _env("ADMIN_PASSWORD", "admin123")

# Adminlarning Telegram ID raqamlari (murojaatlarni qabul qilish uchun)
# Railway uchun ADMIN_IDS="123456789,987654321" shaklida bering
ADMIN_IDS = _parse_admin_ids(_env("ADMIN_IDS", "1746229472"))

# Ball koeffitsientlari
MAJBURIY_KOEFF = 1.1  # Ona tili + Matematika + Tarix (jami 30 savol)
ASOSIY_1_KOEFF = 3.1  # 1-asosiy fan (30 savol)
ASOSIY_2_KOEFF = 2.1  # 2-asosiy fan (30 savol)

MAX_SAVOL = 30  # Har bir guruhda maksimal savol soni

# Franchise to'lov tizimi sozlamalari
# Railway'da KARTA_RAQAMI="8600 1234 5678 9012" shaklida bering
KARTA_RAQAMI = _env("KARTA_RAQAMI", "")
# Oylik to'lov miqdori (so'mda). Standart: 300 000 so'm
OYLIK_NARX = _env_int("OYLIK_NARX", 300_000)

# AI tahlil uchun optional LLM sozlamalari
AI_API_KEY = _env("AI_API_KEY", "")
AI_MODEL = _env("AI_MODEL", "llama-3.3-70b-versatile")
AI_BASE_URL = _env("AI_BASE_URL", "https://api.groq.com/openai/v1")
AI_DAILY_LIMIT = _env_int("AI_DAILY_LIMIT", 50)

# Telegram Mini Web App public URL (Railway'da WEBAPP_URL env variable sifatida bering)
# Masalan: https://your-app.up.railway.app  (https:// prefiksi bilan!)
_webapp_url_raw = _env("WEBAPP_URL", "")
if _webapp_url_raw and not _webapp_url_raw.startswith("http"):
    _webapp_url_raw = "https://" + _webapp_url_raw
WEBAPP_URL = _webapp_url_raw

# Sertifikat verify URL — QR-kodda ishlatiladi
# Railway'da VERIFY_BASE_URL env variable sifatida bering,
# yoki avtomatik WEBAPP_URL dan olinadi
_verify_raw = _env(
    "VERIFY_BASE_URL",
    WEBAPP_URL or "https://bustanlik-ss-testing-system-production.up.railway.app",
)
if _verify_raw and not _verify_raw.startswith("http"):
    _verify_raw = "https://" + _verify_raw
VERIFY_BASE_URL = _verify_raw.rstrip("/")

# Google Sheets eksport sozlamalari
# Railway Variables da GOOGLE_CREDENTIALS_JSON va GOOGLE_SHEETS_ID ni qo'shing
GOOGLE_SHEETS_ID = _env("GOOGLE_SHEETS_ID", "")
GOOGLE_CREDENTIALS_JSON = _env("GOOGLE_CREDENTIALS_JSON", "")

# Brevo email sozlamalari
# Railway Variables da quyidagilarni qo'shing:
#   BREVO_API_KEY      — Brevo dashboard → SMTP & API → API Keys
#   BREVO_SENDER_EMAIL — Brevo'da tasdiqlangan email manzil
#   BREVO_SENDER_NAME  — Xatda ko'rinadigan jo'natuvchi ismi
BREVO_API_KEY      = _env("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = _env("BREVO_SENDER_EMAIL", "sultanovdiyorbek.im@gmail.com")
BREVO_SENDER_NAME  = _env("BREVO_SENDER_NAME", "Bustanlik SS Testing System")

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
