"""
audit_log.py — Tizim bo'ylab amallar jurnali (audit log).

Ham admin/o'qituvchi tomonidan bajarilgan sezilarli amallarni
(o'quvchi o'chirish, ball tahrirlash, to'lov tasdiqlash va h.k.),
ham oddiy foydalanuvchi (o'quvchi/ota-ona) harakatlarini
(tizimga kirish, natija ko'rish, test boshlash va h.k.) bitta
markazlashtirilgan jadvalda saqlaydi.

Ishlatish:
    from audit_log import log_action

    log_action(
        actor_id=callback.from_user.id,
        actor_role="admin",                 # "admin" | "school_admin" | "teacher" | "student" | "parent" | "system"
        action_type="talaba_ochirish",       # ACTION_LABELS dagi kalit (yoki erkin matn)
        actor_name=callback.from_user.full_name,
        target=kod,                          # nimaga nisbatan amal qilindi (masalan o'quvchi kodi)
        details="Sabab: dublikat yozuv",     # qo'shimcha kontekst (ixtiyoriy)
    )

Jadval avtomatik birinchi yozuvda yaratiladi (lazy create), shuningdek
database.py ning init_db() funksiyasi ichida ham chaqiriladi.
"""

from __future__ import annotations

import logging
from tz_utils import now as tz_now

logger = logging.getLogger(__name__)

# ── Rol va amal turlari uchun o'qish-yozish qulay lug'atlar ────────────────

ROLE_LABELS = {
    "admin": "👑 Super admin",
    "school_admin": "🏫 Maktab admin",
    "teacher": "👨‍🏫 O'qituvchi",
    "student": "🎓 O'quvchi",
    "parent": "👪 Ota-ona",
    "system": "⚙️ Tizim",
}

# Amal turi -> (Inson o'qiy oladigan nom, guruh: "admin" | "user")
ACTION_LABELS: dict[str, tuple[str, str]] = {
    # ── Admin/o'qituvchi amallari ───────────────────────────────────────
    "talaba_qoshish":         ("➕ O'quvchi qo'shildi", "admin"),
    "talaba_ochirish":        ("🗑️ O'quvchi o'chirildi", "admin"),
    "talaba_tahrirlash":      ("✏️ O'quvchi ma'lumotlari tahrirlandi", "admin"),
    "natija_qoshish":         ("📝 Natija qo'shildi/tahrirlandi", "admin"),
    "natija_ochirish":        ("🗑️ Natija o'chirildi", "admin"),
    "kalit_qoshish":          ("🔑 Test kaliti qo'shildi", "admin"),
    "kalit_ochirish":         ("🗑️ Test kaliti o'chirildi", "admin"),
    "kalit_tahrirlash":       ("✏️ Test kaliti tahrirlandi", "admin"),
    "sinf_qoshish":           ("➕ Sinf qo'shildi", "admin"),
    "sinf_ochirish":          ("🗑️ Sinf o'chirildi", "admin"),
    "oqituvchi_qoshish":      ("➕ O'qituvchi qo'shildi", "admin"),
    "oqituvchi_ochirish":     ("🗑️ O'qituvchi o'chirildi", "admin"),
    "admin_qoshish":          ("👑 Yangi admin qo'shildi", "admin"),
    "admin_ochirish":         ("🗑️ Admin o'chirildi", "admin"),
    "tolov_tasdiqlash":       ("✅ To'lov tasdiqlandi", "admin"),
    "tolov_rad_etish":        ("❌ To'lov rad etildi", "admin"),
    "narx_ozgartirish":       ("💳 Obuna narxi o'zgartirildi", "admin"),
    "sozlama_ozgartirish":    ("⚙️ Tizim sozlamasi o'zgartirildi", "admin"),
    "xabar_yuborish":         ("📢 Ommaviy xabar yuborildi", "admin"),
    "baza_tozalash":          ("🧹 Ma'lumotlar bazasi tozalandi", "admin"),
    "excel_import":           ("📥 Excel orqali import qilindi", "admin"),
    "sertifikat_sozlama":     ("🎓 Sertifikat sozlamalari o'zgartirildi", "admin"),
    # ── Foydalanuvchi (o'quvchi/ota-ona) amallari ───────────────────────
    "tizimga_kirish":         ("🔓 Botga kirdi (/start)", "user"),
    "royxatdan_otish":        ("🆕 Ro'yxatdan o'tdi", "user"),
    "natija_korish":          ("📊 Natijasini ko'rdi", "user"),
    "profil_korish":          ("👤 Shaxsiy kabinetni ko'rdi", "user"),
    "sertifikat_olish":       ("🎓 Sertifikat yuklab oldi", "user"),
    "reyting_korish":         ("🏆 Reytingni ko'rdi", "user"),
    "mini_test_boshlash":     ("📦 Mini-testni boshladi", "user"),
    "mini_test_yakunlash":    ("✅ Mini-testni yakunladi", "user"),
    "mashq_boshlash":         ("📝 Mashq-quizni boshladi", "user"),
    "apellyatsiya":           ("⚖️ Apellyatsiya yubordi", "user"),
    "murojaat":               ("✍️ Admin bilan bog'landi", "user"),
    "chiqish":                ("🚪 Shaxsiy kabinetdan chiqdi", "user"),
}


def _label_for(action_type: str) -> tuple[str, str]:
    return ACTION_LABELS.get(action_type, (action_type, "user"))


# ── Jadval yaratish ──────────────────────────────────────────────────────

def create_audit_log_table(cursor=None):
    """Audit log jadvalini yaratadi (mavjud bo'lsa o'tkazib yuboriladi)."""
    from database import get_connection, release_connection

    if cursor:
        cur = cursor
    else:
        conn = get_connection()
        cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            actor_id BIGINT,
            actor_role TEXT NOT NULL DEFAULT 'system',
            actor_name TEXT,
            action_type TEXT NOT NULL,
            action_group TEXT NOT NULL DEFAULT 'user',
            target TEXT,
            details TEXT,
            maktab_id INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_action_group ON audit_log(action_group)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC)"
    )

    if not cursor:
        conn.commit()
        cur.close()
        release_connection(conn)


# ── Yozish ────────────────────────────────────────────────────────────────

def log_action(
    actor_id: int | None,
    actor_role: str,
    action_type: str,
    actor_name: str | None = None,
    target: str | None = None,
    details: str | None = None,
    maktab_id: int | None = None,
) -> None:
    """
    Audit jurnaliga bitta yozuv qo'shadi.

    Xatolik yuz bersa (masalan jadval hali yaratilmagan bo'lsa), asosiy
    botning ishlashiga xalaqit bermaslik uchun faqat log'ga yozadi va
    davom etadi — log yozish hech qachon foydalanuvchi oqimini buzmasligi kerak.
    """
    from database import get_connection, release_connection

    _, action_group = _label_for(action_type)

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO audit_log
                (actor_id, actor_role, actor_name, action_type, action_group, target, details, maktab_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (actor_id, actor_role, actor_name, action_type, action_group, target, details, maktab_id, tz_now()),
        )
        conn.commit()
        cur.close()
    except Exception:
        # Jadval mavjud bo'lmasligi mumkin (eski deploy) — joyida yaratib, qayta urinamiz
        try:
            if conn:
                conn.rollback()
            create_audit_log_table()
            conn2 = get_connection()
            cur2 = conn2.cursor()
            cur2.execute(
                """
                INSERT INTO audit_log
                    (actor_id, actor_role, actor_name, action_type, action_group, target, details, maktab_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (actor_id, actor_role, actor_name, action_type, action_group, target, details, maktab_id, tz_now()),
            )
            conn2.commit()
            cur2.close()
            release_connection(conn2)
        except Exception:
            logger.exception("audit_log: yozib bo'lmadi (action_type=%s)", action_type)
    finally:
        if conn:
            release_connection(conn)


# ── O'qish / filtrlash / paginatsiya ────────────────────────────────────────

def get_audit_logs(
    action_group: str | None = None,   # "admin" | "user" | None (hammasi)
    actor_id: int | None = None,
    action_type: str | None = None,
    maktab_id: int | None = None,
    date_from=None,
    date_to=None,
    limit: int = 15,
    offset: int = 0,
) -> list[dict]:
    """Filtrlangan audit yozuvlarini eng yangisidan boshlab qaytaradi."""
    from database import get_connection, release_connection
    import psycopg2.extras

    where = []
    params: list = []

    if action_group:
        where.append("action_group = %s")
        params.append(action_group)
    if actor_id:
        where.append("actor_id = %s")
        params.append(actor_id)
    if action_type:
        where.append("action_type = %s")
        params.append(action_type)
    if maktab_id:
        where.append("maktab_id = %s")
        params.append(maktab_id)
    if date_from:
        where.append("created_at >= %s")
        params.append(date_from)
    if date_to:
        where.append("created_at <= %s")
        params.append(date_to)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            f"""
            SELECT * FROM audit_log
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (*params, limit, offset),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        cur.close()
        release_connection(conn)


def get_audit_log_count(
    action_group: str | None = None,
    actor_id: int | None = None,
    action_type: str | None = None,
    maktab_id: int | None = None,
    date_from=None,
    date_to=None,
) -> int:
    from database import get_connection, release_connection

    where = []
    params: list = []

    if action_group:
        where.append("action_group = %s")
        params.append(action_group)
    if actor_id:
        where.append("actor_id = %s")
        params.append(actor_id)
    if action_type:
        where.append("action_type = %s")
        params.append(action_type)
    if maktab_id:
        where.append("maktab_id = %s")
        params.append(maktab_id)
    if date_from:
        where.append("created_at >= %s")
        params.append(date_from)
    if date_to:
        where.append("created_at <= %s")
        params.append(date_to)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT COUNT(*) FROM audit_log {where_sql}", params)
        return cur.fetchone()[0]
    except Exception:
        return 0
    finally:
        cur.close()
        release_connection(conn)


def format_log_entry(entry: dict) -> str:
    """Bitta audit yozuvini Telegram xabari uchun chiroyli formatlaydi."""
    label, _ = _label_for(entry["action_type"])
    role_label = ROLE_LABELS.get(entry["actor_role"], entry["actor_role"])
    sana = entry["created_at"].strftime("%d.%m.%Y %H:%M") if entry.get("created_at") else "—"

    name = entry.get("actor_name") or "Noma'lum"
    actor_id = entry.get("actor_id") or "—"

    text = f"🕒 <code>{sana}</code>\n{label}\n👤 {role_label}: <b>{name}</b> (<code>{actor_id}</code>)"
    if entry.get("target"):
        text += f"\n🎯 Obyekt: <code>{entry['target']}</code>"
    if entry.get("details"):
        text += f"\nℹ️ {entry['details']}"
    return text
