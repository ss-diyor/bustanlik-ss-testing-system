"""
Mock imtihon natijalari — ma'lumotlar bazasi moduli.

Jadvallar:
  mock_exam_types   — imtihon turlari (admin boshqaradi)
  mock_sections     — har bir turning bo'limlari
  mock_natijalari   — o'quvchi natijalari

Built-in (o'chirib bo'lmaydigan) turlar: IELTS, CEFR, SAT, DTM_MOCK, MILLIY_SERT
Qo'shimcha turlar admin tomonidan qo'shiladi/o'chiriladi.
"""

import psycopg2
import psycopg2.extras
import json
from database import get_connection, release_connection

BUILTIN_EXAM_TYPES = [
    {
        "exam_key": "IELTS",
        "label": "🎯 IELTS",
        "total_max": 9.0,
        "score_type": "band_score",
        "has_level": False,
        "is_builtin": True,
        "sections": [
            {"section_key": "listening", "label": "🎧 Listening", "max_score": 9.0},
            {"section_key": "reading",   "label": "📖 Reading",   "max_score": 9.0},
            {"section_key": "writing",   "label": "✍️ Writing",   "max_score": 9.0},
            {"section_key": "speaking",  "label": "🗣 Speaking",  "max_score": 9.0},
        ],
    },
    {
        "exam_key": "CEFR",
        "label": "🌍 CEFR",
        # CEFR: har bir section 0–75 bo'ladi, umumiy esa o'rtacha (4 section yig'indisi / 4)
        # Shuning uchun Umumiy max ham 75.0.
        "total_max": 75.0,
        "score_type": "direct_score",
        "has_level": True,
        "levels": "A1,A2,B1,B2,C1,C2",
        "is_builtin": True,
        "sections": [
            {"section_key": "listening", "label": "🎧 Listening", "max_score": 75.0},
            {"section_key": "reading",   "label": "📖 Reading",   "max_score": 75.0},
            {"section_key": "writing",   "label": "✍️ Writing",   "max_score": 75.0},
            {"section_key": "speaking",  "label": "🗣 Speaking",  "max_score": 75.0},
        ],
    },
    {
        "exam_key": "SAT",
        "label": "📝 SAT",
        "total_max": 1600.0,
        "score_type": "direct_score",
        "has_level": False,
        "is_builtin": True,
        "sections": [
            {"section_key": "reading_writing", "label": "📖 Reading & Writing", "max_score": 800.0},
            {"section_key": "math",            "label": "📐 Math",               "max_score": 800.0},
        ],
    },
    {
        "exam_key": "DTM_MOCK",
        "label": "🎓 DTM Mock",
        "total_max": 189.0,
        "score_type": "correct_answers",
        "has_level": False,
        "is_builtin": True,
        "sections": [
            {"section_key": "majburiy",  "label": "📘 Majburiy fanlar", "max_score": 30.0},
            {"section_key": "asosiy_1", "label": "📗 1-asosiy fan",    "max_score": 30.0},
            {"section_key": "asosiy_2", "label": "📙 2-asosiy fan",    "max_score": 30.0},
        ],
    },
    {
        "exam_key": "MILLIY_SERT",
        "label": "🏅 Milliy sertifikat",
        "total_max": None,
        "score_type": "direct_score",
        "has_level": False,
        "is_builtin": True,
        "sections": [
            {"section_key": "ball", "label": "📊 Ball", "max_score": 100.0},
        ],
    },
]


def create_mock_tables():
    conn = get_connection()
    cur = conn.cursor()

    # Eski bazalarda (legacy) `exam_type` nomi ishlatilgan bo‘lishi mumkin.
    # Avval parent jadvalni yaratamiz, keyin kerak bo‘lsa ustunlarni migrate qilamiz,
    # shundan keyingina FK'li jadvallarni yaratamiz.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_exam_types (
            id          SERIAL PRIMARY KEY,
            exam_key    TEXT UNIQUE NOT NULL,
            label       TEXT NOT NULL,
            total_max   REAL,
            score_type  TEXT NOT NULL DEFAULT 'direct_score',
            has_level   BOOLEAN NOT NULL DEFAULT FALSE,
            levels      TEXT,
            is_builtin  BOOLEAN NOT NULL DEFAULT FALSE,
            is_active   BOOLEAN NOT NULL DEFAULT TRUE,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- Legacy migration: exam_type -> exam_key (mock_exam_types) ---
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='mock_exam_types'
        """
    )
    cols = {r[0] for r in cur.fetchall()}
    if "exam_key" not in cols and "exam_type" in cols:
        cur.execute("ALTER TABLE mock_exam_types RENAME COLUMN exam_type TO exam_key")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_sections (
            id          SERIAL PRIMARY KEY,
            exam_key    TEXT NOT NULL REFERENCES mock_exam_types(exam_key) ON DELETE CASCADE,
            section_key TEXT NOT NULL,
            label       TEXT NOT NULL,
            max_score   REAL,
            sort_order  INTEGER NOT NULL DEFAULT 0,
            UNIQUE (exam_key, section_key)
        )
    """)

    # --- Legacy migration: exam_type -> exam_key (mock_sections) ---
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='mock_sections'
        """
    )
    cols = {r[0] for r in cur.fetchall()}
    if "exam_key" not in cols and "exam_type" in cols:
        cur.execute("ALTER TABLE mock_sections RENAME COLUMN exam_type TO exam_key")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_natijalari (
            id           SERIAL PRIMARY KEY,
            talaba_kod   TEXT NOT NULL,
            exam_key     TEXT NOT NULL,
            exam_label   TEXT,
            sections     JSONB NOT NULL DEFAULT '{}',
            umumiy_ball  REAL,
            level_label  TEXT,
            subject_name TEXT,
            notes        TEXT,
            test_sanasi  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_id     BIGINT,
            FOREIGN KEY (talaba_kod) REFERENCES talabalar(kod) ON DELETE CASCADE
        )
    """)

    # --- Legacy migration: exam_type -> exam_key (mock_natijalari) ---
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='mock_natijalari'
        """
    )
    cols = {r[0] for r in cur.fetchall()}
    if "exam_key" not in cols and "exam_type" in cols:
        cur.execute("ALTER TABLE mock_natijalari RENAME COLUMN exam_type TO exam_key")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_mock_nat_kod  ON mock_natijalari(talaba_kod)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mock_nat_key  ON mock_natijalari(exam_key)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mock_nat_sana ON mock_natijalari(test_sanasi)")
    conn.commit()

    _seed_builtin(cur, conn)
    cur.close()
    release_connection(conn)


def _seed_builtin(cur, conn):
    for et in BUILTIN_EXAM_TYPES:
        cur.execute(
            """
            INSERT INTO mock_exam_types
                (exam_key, label, total_max, score_type, has_level, levels, is_builtin)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (exam_key) DO UPDATE SET
                label      = EXCLUDED.label,
                total_max  = EXCLUDED.total_max,
                score_type = EXCLUDED.score_type,
                has_level  = EXCLUDED.has_level,
                levels     = EXCLUDED.levels,
                is_builtin = EXCLUDED.is_builtin
            """,
            (
                et["exam_key"], et["label"], et.get("total_max"),
                et["score_type"], et.get("has_level", False),
                et.get("levels"), et["is_builtin"],
            ),
        )
        for i, sec in enumerate(et.get("sections", [])):
            cur.execute(
                """
                INSERT INTO mock_sections (exam_key, section_key, label, max_score, sort_order)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (exam_key, section_key) DO UPDATE SET
                    label      = EXCLUDED.label,
                    max_score  = EXCLUDED.max_score,
                    sort_order = EXCLUDED.sort_order
                """,
                (et["exam_key"], sec["section_key"], sec["label"], sec.get("max_score"), i),
            )
    conn.commit()


# ─── EXAM TYPE CRUD ───────────────────────────────────────────

def exam_types_ol(faqat_aktiv: bool = True) -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if faqat_aktiv:
        cur.execute(
            "SELECT * FROM mock_exam_types WHERE is_active=TRUE ORDER BY is_builtin DESC, label"
        )
    else:
        cur.execute("SELECT * FROM mock_exam_types ORDER BY is_builtin DESC, label")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def exam_type_ol(exam_key: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM mock_exam_types WHERE exam_key=%s", (exam_key,))
    et = cur.fetchone()
    if not et:
        cur.close(); release_connection(conn); return None
    et = dict(et)
    cur.execute(
        "SELECT * FROM mock_sections WHERE exam_key=%s ORDER BY sort_order", (exam_key,)
    )
    et["sections"] = [dict(s) for s in cur.fetchall()]
    if et.get("levels"):
        et["levels_list"] = [l.strip() for l in et["levels"].split(",")]
    cur.close()
    release_connection(conn)
    return et


def exam_type_qosh(
    exam_key: str,
    label: str,
    sections: list,        # [{"section_key":"...", "label":"...", "max_score":100}]
    total_max: float = None,
    score_type: str = "direct_score",
    has_level: bool = False,
    levels: str = None,
) -> tuple:
    """Qaytaradi: (True, "ok") yoki (False, "xato matni")"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO mock_exam_types
                (exam_key, label, total_max, score_type, has_level, levels, is_builtin)
            VALUES (%s, %s, %s, %s, %s, %s, FALSE)
            """,
            (exam_key, label, total_max, score_type, has_level, levels),
        )
        for i, sec in enumerate(sections):
            cur.execute(
                """
                INSERT INTO mock_sections (exam_key, section_key, label, max_score, sort_order)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (exam_key, sec["section_key"], sec["label"], sec.get("max_score"), i),
            )
        conn.commit()
        return True, "ok"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        cur.close(); release_connection(conn)


def exam_type_ochir(exam_key: str) -> tuple:
    """Qaytaradi: (True, xabar) yoki (False, xabar)"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT is_builtin FROM mock_exam_types WHERE exam_key=%s", (exam_key,))
    row = cur.fetchone()
    if not row:
        cur.close(); release_connection(conn)
        return False, "Topilmadi."
    if row[0]:
        cur.close(); release_connection(conn)
        return False, "Standart (built-in) turlarni o'chirib bo'lmaydi."

    cur.execute("SELECT COUNT(*) FROM mock_natijalari WHERE exam_key=%s", (exam_key,))
    count = cur.fetchone()[0]
    try:
        cur.execute("DELETE FROM mock_exam_types WHERE exam_key=%s", (exam_key,))
        conn.commit()
        msg = "O'chirildi."
        if count:
            msg = f"O'chirildi. ({count} ta natija ham o'chirildi)"
        return True, msg
    except Exception as e:
        conn.rollback()
        return False, f"Xatolik: {e}"
    finally:
        cur.close(); release_connection(conn)


def exam_type_holat(exam_key: str, aktiv: bool) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE mock_exam_types SET is_active=%s WHERE exam_key=%s", (aktiv, exam_key)
    )
    ok = cur.rowcount > 0
    conn.commit()
    cur.close(); release_connection(conn)
    return ok


# ─── MOCK NATIJASI CRUD ───────────────────────────────────────

def mock_natija_qosh(
    talaba_kod: str,
    exam_key: str,
    sections: dict,
    umumiy_ball: float = None,
    level_label: str = None,
    subject_name: str = None,
    notes: str = None,
    admin_id: int = None,
) -> int:
    def _num(val):
        # Custom section format qo'llab-quvvatlash:
        # sections = {key: number} yoki {key: {"value": number, ...}}
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, dict):
            v = val.get("value")
            if isinstance(v, (int, float)):
                return float(v)
        return None

    def _max(val):
        if isinstance(val, dict):
            mx = val.get("max")
            if isinstance(mx, (int, float)):
                return float(mx)
        return None

    et = exam_type_ol(exam_key) or {}
    exam_label = et.get("label", exam_key)

    if umumiy_ball is None and et.get("total_max"):
        if exam_key == "DTM_MOCK":
            try:
                from config import MAJBURIY_KOEFF, ASOSIY_1_KOEFF, ASOSIY_2_KOEFF
                maj = _num(sections.get("majburiy")) or 0
                as1 = _num(sections.get("asosiy_1")) or 0
                as2 = _num(sections.get("asosiy_2")) or 0
                maj_max = _max(sections.get("majburiy"))
                as1_max = _max(sections.get("asosiy_1"))
                as2_max = _max(sections.get("asosiy_2"))

                # DTM Mock uchun ikki xil kiritish uchraydi:
                # 1) 0-30 oralig'idagi to'g'ri javoblar soni
                # 2) allaqachon koeffitsientlangan ballar (masalan 88 / 93)
                #
                # Agar qiymat yoki max 30 dan katta bo'lsa, u tayyor ball deb olinadi
                # va qayta ko'paytirilmaydi.
                is_weighted_input = any(
                    item is not None and item > 30
                    for item in (maj, as1, as2, maj_max, as1_max, as2_max)
                )
                if is_weighted_input:
                    umumiy_ball = round(maj + as1 + as2, 2)
                else:
                    umumiy_ball = round(
                        maj * MAJBURIY_KOEFF
                        + as1 * ASOSIY_1_KOEFF
                        + as2 * ASOSIY_2_KOEFF,
                        2,
                    )
            except Exception:
                pass
        elif exam_key == "IELTS":
            vals = [_num(v) for v in sections.values()]
            vals = [v for v in vals if v is not None]
            if vals:
                umumiy_ball = round(round(sum(vals) / len(vals) * 2) / 2, 1)
        elif exam_key == "CEFR":
            vals = [_num(v) for v in sections.values()]
            vals = [v for v in vals if v is not None]
            if vals:
                umumiy_ball = round(sum(vals) / len(vals), 1)
        else:
            vals = [_num(v) for v in sections.values()]
            vals = [v for v in vals if v is not None]
            if vals:
                umumiy_ball = round(sum(vals), 1)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO mock_natijalari
            (talaba_kod, exam_key, exam_label, sections, umumiy_ball,
             level_label, subject_name, notes, admin_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            talaba_kod, exam_key, exam_label,
            json.dumps(sections), umumiy_ball,
            level_label, subject_name, notes, admin_id,
        ),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); release_connection(conn)
    return new_id


def mock_natijalari_ol(talaba_kod: str, exam_key: str = None, limit: int = 10) -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if exam_key:
        cur.execute(
            "SELECT * FROM mock_natijalari WHERE talaba_kod=%s AND exam_key=%s "
            "ORDER BY test_sanasi DESC LIMIT %s",
            (talaba_kod, exam_key, limit),
        )
    else:
        cur.execute(
            "SELECT * FROM mock_natijalari WHERE talaba_kod=%s "
            "ORDER BY test_sanasi DESC LIMIT %s",
            (talaba_kod, limit),
        )
    rows = cur.fetchall()
    cur.close(); release_connection(conn)
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("sections"), str):
            d["sections"] = json.loads(d["sections"])
        result.append(d)
    return result


def mock_songi_natija(talaba_kod: str, exam_key: str = None):
    r = mock_natijalari_ol(talaba_kod, exam_key, limit=1)
    return r[0] if r else None


def mock_natija_turlari(talaba_kod: str) -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT exam_key, exam_label,
               COUNT(*) AS soni,
               MAX(test_sanasi) AS oxirgi_sana
        FROM mock_natijalari
        WHERE talaba_kod=%s
        GROUP BY exam_key, exam_label
        ORDER BY oxirgi_sana DESC
        """,
        (talaba_kod,),
    )
    rows = cur.fetchall()
    cur.close(); release_connection(conn)
    return [dict(r) for r in rows]


def mock_natija_ochir(natija_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM mock_natijalari WHERE id=%s", (natija_id,))
    ok = cur.rowcount > 0
    conn.commit()
    cur.close(); release_connection(conn)
    return ok


# ─── FORMATLASH ───────────────────────────────────────────────

def format_mock_natija_matn(natija: dict, et: dict = None) -> str:
    if et is None:
        et = exam_type_ol(natija.get("exam_key", "")) or {}
    sana = str(natija.get("test_sanasi", ""))[:10]
    exam_label = natija.get("exam_label") or et.get("label", "Mock")
    sections = natija.get("sections", {})

    lines = [f"📋 <b>{exam_label}</b>", f"📅 Sana: <b>{sana}</b>", ""]

    if natija.get("subject_name"):
        lines.append(f"📚 Fan: <b>{natija['subject_name']}</b>")

    sec_map = {s["section_key"]: s for s in et.get("sections", [])}
    for sec_key, sec_val in sections.items():
        # sections ikki xil bo‘lishi mumkin:
        # 1) { "listening": 8.0, ... }
        # 2) { "listening": {"label":"🎧 Listening","value":8.0,"max":9.0}, ... }
        if isinstance(sec_val, dict) and "value" in sec_val:
            label = sec_val.get("label") or sec_map.get(sec_key, {}).get("label") or f"📊 {sec_key.capitalize()}"
            max_s = sec_val.get("max")
            val = sec_val.get("value")
        else:
            sec_info = sec_map.get(sec_key, {})
            label = sec_info.get("label", f"📊 {sec_key.capitalize()}")
            max_s = sec_info.get("max_score")
            val = sec_val

        if max_s is not None:
            lines.append(f"{label}: <b>{val}</b> / {max_s}")
        else:
            lines.append(f"{label}: <b>{val}</b>")

    umumiy = natija.get("umumiy_ball")
    if umumiy is not None:
        total_max = et.get("total_max")
        if total_max:
            lines.append(f"\n🏆 <b>Umumiy: {umumiy} / {total_max}</b>")
        else:
            lines.append(f"\n🏆 <b>Umumiy: {umumiy}</b>")

    if natija.get("level_label"):
        lines.append(f"🎯 Daraja: <b>{natija['level_label']}</b>")

    if natija.get("notes"):
        lines.append(f"\n📝 Izoh: {natija['notes']}")

    return "\n".join(lines)
