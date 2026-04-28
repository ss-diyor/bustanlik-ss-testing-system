"""
Mock imtihon natijalari uchun ma'lumotlar bazasi funksiyalari.

Qo'llab-quvvatlanadigan imtihon turlari:
  - DTM_MOCK    : Alohida fanlardan DTM uslubidagi mock (majburiy + asosiy1 + asosiy2)
  - INGLIZ_TILI : Ingliz tili mock (bir fan)
  - ONA_TILI    : Ona tili mock
  - MATEMATIKA  : Matematika mock
  - CEFR        : A1/A2/B1/B2/C1/C2 bosqichlari
  - SAT         : Reading+Writing, Math bo'limlari
  - MILLIY_SERT : Milliy sertifikat (fan bo'yicha ballar)
  - IELTS       : Listening, Reading, Writing, Speaking, Overall
  - CUSTOM      : Istalgan fan, erkin bo'limlar bilan
"""

import psycopg2
import psycopg2.extras
import json
from datetime import datetime
from database import get_connection, release_connection

# ─────────────────────────────────────────────────────────────
# IMTIHON TURLARI KONFIGURATSIYASI
# ─────────────────────────────────────────────────────────────

EXAM_TYPES = {
    "DTM_MOCK": {
        "label": "🎓 DTM Mock",
        "sections": ["majburiy", "asosiy_1", "asosiy_2"],
        "section_labels": {
            "majburiy": "📘 Majburiy fanlar",
            "asosiy_1": "📗 1-asosiy fan",
            "asosiy_2": "📙 2-asosiy fan",
        },
        "max_scores": {"majburiy": 30, "asosiy_1": 30, "asosiy_2": 30},
        "has_total": True,
        "total_label": "Umumiy ball (189 dan)",
        "total_max": 189,
        "score_type": "correct_answers",  # to'g'ri javoblar soni
    },
    "INGLIZ_TILI": {
        "label": "🇬🇧 Ingliz tili mock",
        "sections": ["ball"],
        "section_labels": {"ball": "📊 Ball"},
        "max_scores": {"ball": 100},
        "has_total": False,
        "score_type": "direct_score",
    },
    "ONA_TILI": {
        "label": "📖 Ona tili mock",
        "sections": ["ball"],
        "section_labels": {"ball": "📊 Ball"},
        "max_scores": {"ball": 100},
        "has_total": False,
        "score_type": "direct_score",
    },
    "MATEMATIKA": {
        "label": "📐 Matematika mock",
        "sections": ["ball"],
        "section_labels": {"ball": "📊 Ball"},
        "max_scores": {"ball": 100},
        "has_total": False,
        "score_type": "direct_score",
    },
    "CEFR": {
        "label": "🌍 CEFR",
        "sections": ["listening", "reading", "writing", "speaking"],
        "section_labels": {
            "listening": "🎧 Listening",
            "reading": "📖 Reading",
            "writing": "✍️ Writing",
            "speaking": "🗣 Speaking",
        },
        "max_scores": {
            "listening": 25,
            "reading": 25,
            "writing": 25,
            "speaking": 25,
        },
        "has_total": True,
        "total_label": "Umumiy ball (100 dan)",
        "total_max": 100,
        "score_type": "direct_score",
        "has_level": True,
        "levels": ["A1", "A2", "B1", "B2", "C1", "C2"],
    },
    "SAT": {
        "label": "📝 SAT",
        "sections": ["reading_writing", "math"],
        "section_labels": {
            "reading_writing": "📖 Reading & Writing",
            "math": "📐 Math",
        },
        "max_scores": {"reading_writing": 800, "math": 800},
        "has_total": True,
        "total_label": "Umumiy ball (1600 dan)",
        "total_max": 1600,
        "score_type": "direct_score",
    },
    "MILLIY_SERT": {
        "label": "🏅 Milliy sertifikat",
        "sections": ["fan_nomi", "ball"],
        "section_labels": {
            "fan_nomi": "📚 Fan nomi",
            "ball": "📊 Ball",
        },
        "max_scores": {"ball": 100},
        "has_total": False,
        "score_type": "direct_score",
        "has_subject": True,
    },
    "IELTS": {
        "label": "🎯 IELTS",
        "sections": ["listening", "reading", "writing", "speaking"],
        "section_labels": {
            "listening": "🎧 Listening",
            "reading": "📖 Reading",
            "writing": "✍️ Writing",
            "speaking": "🗣 Speaking",
        },
        "max_scores": {
            "listening": 9,
            "reading": 9,
            "writing": 9,
            "speaking": 9,
        },
        "has_total": True,
        "total_label": "Overall Band Score (9 dan)",
        "total_max": 9,
        "score_type": "band_score",
    },
    "CUSTOM": {
        "label": "⚙️ Boshqa imtihon",
        "sections": [],  # dinamik, admin kiritadi
        "section_labels": {},
        "max_scores": {},
        "has_total": False,
        "score_type": "direct_score",
    },
}


# ─────────────────────────────────────────────────────────────
# JADVAL YARATISH
# ─────────────────────────────────────────────────────────────

def create_mock_tables():
    """Mock imtihon natijalari jadvallarini yaratish."""
    conn = get_connection()
    cur = conn.cursor()

    # Asosiy mock natijalari jadvali
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_natijalari (
            id SERIAL PRIMARY KEY,
            talaba_kod TEXT NOT NULL,
            exam_type TEXT NOT NULL,
            exam_label TEXT,
            sections JSONB NOT NULL DEFAULT '{}',
            umumiy_ball REAL,
            level_label TEXT,
            subject_name TEXT,
            notes TEXT,
            test_sanasi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_id BIGINT,
            FOREIGN KEY (talaba_kod) REFERENCES talabalar (kod)
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_mock_natijalari_kod ON mock_natijalari(talaba_kod)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_mock_natijalari_type ON mock_natijalari(exam_type)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_mock_natijalari_sana ON mock_natijalari(test_sanasi)"
    )

    conn.commit()
    cur.close()
    release_connection(conn)


# ─────────────────────────────────────────────────────────────
# MOCK NATIJASINI QO'SHISH
# ─────────────────────────────────────────────────────────────

def mock_natija_qosh(
    talaba_kod: str,
    exam_type: str,
    sections: dict,
    umumiy_ball: float = None,
    level_label: str = None,
    subject_name: str = None,
    notes: str = None,
    admin_id: int = None,
    exam_label: str = None,
) -> int:
    """
    Yangi mock natijasini saqlash.
    sections — {"listening": 7.5, "reading": 8.0, ...} ko'rinishida
    Qaytaradi: yangi yozuv id si
    """
    cfg = EXAM_TYPES.get(exam_type, EXAM_TYPES["CUSTOM"])
    if exam_label is None:
        exam_label = cfg["label"]

    # Umumiy ballni avtomatik hisoblash (agar berilmagan bo'lsa)
    if umumiy_ball is None and cfg.get("has_total"):
        if exam_type == "DTM_MOCK":
            from config import MAJBURIY_KOEFF, ASOSIY_1_KOEFF, ASOSIY_2_KOEFF
            maj = sections.get("majburiy", 0)
            as1 = sections.get("asosiy_1", 0)
            as2 = sections.get("asosiy_2", 0)
            umumiy_ball = round(
                maj * MAJBURIY_KOEFF + as1 * ASOSIY_1_KOEFF + as2 * ASOSIY_2_KOEFF, 2
            )
        elif exam_type == "IELTS":
            vals = [v for v in sections.values() if isinstance(v, (int, float))]
            umumiy_ball = round(sum(vals) / len(vals) * 2) / 2 if vals else None
        elif exam_type in ("CEFR", "SAT"):
            vals = [v for v in sections.values() if isinstance(v, (int, float))]
            umumiy_ball = round(sum(vals), 1) if vals else None

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO mock_natijalari
            (talaba_kod, exam_type, exam_label, sections, umumiy_ball,
             level_label, subject_name, notes, admin_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            talaba_kod,
            exam_type,
            exam_label,
            json.dumps(sections),
            umumiy_ball,
            level_label,
            subject_name,
            notes,
            admin_id,
        ),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    release_connection(conn)
    return new_id


# ─────────────────────────────────────────────────────────────
# NATIJALARNI O'QISH
# ─────────────────────────────────────────────────────────────

def mock_natijalari_ol(talaba_kod: str, exam_type: str = None, limit: int = 10):
    """O'quvchining mock natijalarini qaytaradi."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if exam_type:
        cur.execute(
            """
            SELECT * FROM mock_natijalari
            WHERE talaba_kod = %s AND exam_type = %s
            ORDER BY test_sanasi DESC
            LIMIT %s
            """,
            (talaba_kod, exam_type, limit),
        )
    else:
        cur.execute(
            """
            SELECT * FROM mock_natijalari
            WHERE talaba_kod = %s
            ORDER BY test_sanasi DESC
            LIMIT %s
            """,
            (talaba_kod, limit),
        )
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    # sections JSONB ni dict ga o'girish
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("sections"), str):
            d["sections"] = json.loads(d["sections"])
        result.append(d)
    return result


def mock_songi_natija(talaba_kod: str, exam_type: str = None):
    """Eng oxirgi mock natijasini qaytaradi."""
    results = mock_natijalari_ol(talaba_kod, exam_type, limit=1)
    return results[0] if results else None


def mock_natija_turlari(talaba_kod: str):
    """O'quvchida qaysi turdagi mock natijalari borligini qaytaradi."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT DISTINCT exam_type, exam_label, COUNT(*) as soni,
               MAX(test_sanasi) as oxirgi_sana
        FROM mock_natijalari
        WHERE talaba_kod = %s
        GROUP BY exam_type, exam_label
        ORDER BY oxirgi_sana DESC
        """,
        (talaba_kod,),
    )
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def mock_natija_ochir(natija_id: int) -> bool:
    """Bitta mock natijasini o'chirish."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM mock_natijalari WHERE id = %s", (natija_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    cur.close()
    release_connection(conn)
    return deleted


def mock_statistika_sinf(sinf: str, exam_type: str):
    """Sinf bo'yicha mock statistikasi."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT t.ismlar, t.kod, mn.umumiy_ball, mn.sections, mn.test_sanasi, mn.level_label
        FROM mock_natijalari mn
        JOIN talabalar t ON mn.talaba_kod = t.kod
        WHERE t.sinf = %s AND mn.exam_type = %s
          AND mn.id IN (
            SELECT DISTINCT ON (talaba_kod) id
            FROM mock_natijalari
            WHERE exam_type = %s
            ORDER BY talaba_kod, test_sanasi DESC
          )
        ORDER BY mn.umumiy_ball DESC NULLS LAST
        """,
        (sinf, exam_type, exam_type),
    )
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("sections"), str):
            d["sections"] = json.loads(d["sections"])
        result.append(d)
    return result


# ─────────────────────────────────────────────────────────────
# YORDAMCHI FUNKSIYALAR
# ─────────────────────────────────────────────────────────────

def format_mock_natija_matn(natija: dict) -> str:
    """Mock natijasini chiroyli matn ko'rinishida qaytaradi."""
    exam_type = natija.get("exam_type", "CUSTOM")
    cfg = EXAM_TYPES.get(exam_type, EXAM_TYPES["CUSTOM"])
    sections = natija.get("sections", {})
    sana = str(natija.get("test_sanasi", ""))[:10]
    exam_label = natija.get("exam_label") or cfg["label"]

    lines = [f"📋 <b>{exam_label}</b>", f"📅 Sana: <b>{sana}</b>", ""]

    # Subject (Milliy sertifikat uchun)
    if natija.get("subject_name"):
        lines.append(f"📚 Fan: <b>{natija['subject_name']}</b>")

    # Bo'limlar bo'yicha natijalar
    section_labels = cfg.get("section_labels", {})
    max_scores = cfg.get("max_scores", {})

    for sec_key, sec_val in sections.items():
        label = section_labels.get(sec_key, f"📊 {sec_key.capitalize()}")
        max_val = max_scores.get(sec_key)
        if max_val is not None:
            lines.append(f"{label}: <b>{sec_val}</b> / {max_val}")
        else:
            lines.append(f"{label}: <b>{sec_val}</b>")

    # Umumiy ball
    if natija.get("umumiy_ball") is not None:
        total_label = cfg.get("total_label", "Umumiy ball")
        total_max = cfg.get("total_max")
        if total_max:
            lines.append(f"\n🏆 <b>{total_label}: {natija['umumiy_ball']} / {total_max}</b>")
        else:
            lines.append(f"\n🏆 <b>Umumiy: {natija['umumiy_ball']}</b>")

    # Daraja (CEFR uchun)
    if natija.get("level_label"):
        lines.append(f"🎯 Daraja: <b>{natija['level_label']}</b>")

    # Izoh
    if natija.get("notes"):
        lines.append(f"\n📝 Izoh: {natija['notes']}")

    return "\n".join(lines)
