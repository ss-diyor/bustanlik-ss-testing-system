"""
Mock imtihon topshirish tizimi — savollar banki, talaba urinishlari (attempts),
javoblarni avtomatik tekshirish va admin tekshiruvi uchun ma'lumotlar bazasi moduli.

Jadvallar:
  mock_tests             — har bir aniq mock test nusxasi (masalan "IELTS Mock #1")
  mock_test_sections     — testning bo'limlari (listening/reading/writing)
  mock_test_questions    — savollar banki (mcq/matching/fill_blank/true_false)
  mock_attempts          — talabaning bitta urinishi (boshlandi -> yuborildi -> tekshirildi)
  mock_attempt_answers   — Listening/Reading uchun talaba javoblari (avtomatik tekshiriladi)
  mock_attempt_essays    — Writing uchun talaba insholari (qo'lda tekshiriladi)

MUHIM: yakuniy ball (admin tekshirib, Excel orqali kiritgandan keyin) mavjud
`mock_database.py` ichidagi `mock_natija_qosh()` orqali `mock_natijalari` jadvaliga
yoziladi — shu bilan mavjud natija ko'rsatish, statistika va eksport tizimi
o'zgarishsiz ishlayveradi. Bu modul faqat savol-javob va urinish bosqichini boshqaradi.
"""

import json
import secrets
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
from database import get_connection, release_connection
from dtm_scoring import (
    DTM_EXAM_KEY,
    DTM_SECTION_RULES,
    dtm_ball_hisobla,
    dtm_sections_natijasi,
)


# ─── JADVALLAR ─────────────────────────────────────────────────

def create_mock_exam_engine_tables(cursor=None):
    if cursor:
        cur = cursor
    else:
        conn = get_connection()
        cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_tests (
            id               SERIAL PRIMARY KEY,
            exam_key         TEXT NOT NULL REFERENCES mock_exam_types(exam_key) ON DELETE CASCADE,
            title            TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL DEFAULT 60,
            is_active        BOOLEAN NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_test_sections (
            id            SERIAL PRIMARY KEY,
            test_id       INTEGER NOT NULL REFERENCES mock_tests(id) ON DELETE CASCADE,
            section_key   TEXT NOT NULL,
            label         TEXT NOT NULL,
            audio_url     TEXT,
            instructions  TEXT,
            sort_order    INTEGER NOT NULL DEFAULT 0,
            UNIQUE (test_id, section_key)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_test_questions (
            id              SERIAL PRIMARY KEY,
            section_id      INTEGER NOT NULL REFERENCES mock_test_sections(id) ON DELETE CASCADE,
            question_type   TEXT NOT NULL,
            question_text   TEXT NOT NULL,
            content         JSONB NOT NULL DEFAULT '{}',
            correct_answer  JSONB NOT NULL DEFAULT '{}',
            points          REAL NOT NULL DEFAULT 1,
            sort_order      INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_attempts (
            id             SERIAL PRIMARY KEY,
            talaba_kod     TEXT NOT NULL REFERENCES talabalar(kod) ON DELETE CASCADE,
            test_id        INTEGER NOT NULL REFERENCES mock_tests(id) ON DELETE CASCADE,
            status         TEXT NOT NULL DEFAULT 'in_progress',
            started_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            submitted_at   TIMESTAMP,
            reviewed_at    TIMESTAMP,
            admin_id       BIGINT,
            mock_natija_id INTEGER REFERENCES mock_natijalari(id) ON DELETE SET NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_attempt_answers (
            id              SERIAL PRIMARY KEY,
            attempt_id      INTEGER NOT NULL REFERENCES mock_attempts(id) ON DELETE CASCADE,
            question_id     INTEGER NOT NULL REFERENCES mock_test_questions(id) ON DELETE CASCADE,
            student_answer  JSONB,
            is_correct      BOOLEAN,
            answered_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (attempt_id, question_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_attempt_essays (
            id           SERIAL PRIMARY KEY,
            attempt_id   INTEGER NOT NULL REFERENCES mock_attempts(id) ON DELETE CASCADE,
            section_id   INTEGER NOT NULL REFERENCES mock_test_sections(id) ON DELETE CASCADE,
            essay_text   TEXT NOT NULL DEFAULT '',
            word_count   INTEGER NOT NULL DEFAULT 0,
            saved_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (attempt_id, section_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_web_sessions (
            token       TEXT PRIMARY KEY,
            talaba_kod  TEXT NOT NULL REFERENCES talabalar(kod) ON DELETE CASCADE,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at  TIMESTAMP NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mock_sessions_kod ON mock_web_sessions(talaba_kod)")

    # Tayyor HTML sahifa (masalan tayyor IELTS Listening/Reading/Writing varog'i) rejimi
    cur.execute("ALTER TABLE mock_test_sections ADD COLUMN IF NOT EXISTS custom_html TEXT")
    cur.execute("ALTER TABLE mock_test_sections ADD COLUMN IF NOT EXISTS custom_answer_key JSONB")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS mock_attempt_custom_answers (
            id           SERIAL PRIMARY KEY,
            attempt_id   INTEGER NOT NULL REFERENCES mock_attempts(id) ON DELETE CASCADE,
            section_id   INTEGER NOT NULL REFERENCES mock_test_sections(id) ON DELETE CASCADE,
            raw_answers  JSONB NOT NULL DEFAULT '{}',
            updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (attempt_id, section_id)
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_mock_attempts_kod ON mock_attempts(talaba_kod)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mock_attempts_status ON mock_attempts(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mock_answers_attempt ON mock_attempt_answers(attempt_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mock_essays_attempt ON mock_attempt_essays(attempt_id)")

    if not cursor:
        conn.commit()
        cur.close()
        release_connection(conn)


# ─── TEST CRUD ──────────────────────────────────────────────────

def test_yarat(exam_key: str, title: str, duration_minutes: int = 60) -> int:
    if duration_minutes <= 0:
        raise ValueError("Imtihon davomiyligi 0 dan katta bo'lishi kerak")
    conn = get_connection()
    cur = conn.cursor()
    is_active = exam_key != DTM_EXAM_KEY
    cur.execute(
        """
        INSERT INTO mock_tests (exam_key, title, duration_minutes, is_active)
        VALUES (%s,%s,%s,%s) RETURNING id
        """,
        (exam_key, title, duration_minutes, is_active),
    )
    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); release_connection(conn)
    return new_id


def testlar_royhati(exam_key: str = None, faqat_aktiv: bool = True) -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sql = "SELECT * FROM mock_tests WHERE TRUE"
    params = []
    if exam_key:
        sql += " AND exam_key=%s"
        params.append(exam_key)
    if faqat_aktiv:
        sql += " AND is_active=TRUE"
    sql += " ORDER BY created_at DESC"
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close(); release_connection(conn)
    return [dict(r) for r in rows]


def test_ol(test_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM mock_tests WHERE id=%s", (test_id,))
    test = cur.fetchone()
    if not test:
        cur.close(); release_connection(conn)
        return None
    test = dict(test)
    cur.execute(
        "SELECT * FROM mock_test_sections WHERE test_id=%s ORDER BY sort_order",
        (test_id,),
    )
    test["sections"] = [dict(s) for s in cur.fetchall()]
    cur.close(); release_connection(conn)
    return test


def dtm_test_tayyorligi(test_id: int) -> tuple[bool, str]:
    """DTM testida aynan 30+30+30 savol va xavfsiz server savollari borligini tekshiradi."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT exam_key FROM mock_tests WHERE id=%s", (test_id,))
    test = cur.fetchone()
    if not test:
        cur.close(); release_connection(conn)
        return False, "Test topilmadi"
    if test["exam_key"] != DTM_EXAM_KEY:
        cur.close(); release_connection(conn)
        return True, "ok"

    cur.execute(
        """
        SELECT s.section_key, s.custom_html, COUNT(q.id) AS questions_count
        FROM mock_test_sections s
        LEFT JOIN mock_test_questions q ON q.section_id=s.id
        WHERE s.test_id=%s
        GROUP BY s.id
        """,
        (test_id,),
    )
    sections = {r["section_key"]: dict(r) for r in cur.fetchall()}
    cur.close(); release_connection(conn)

    for key, rule in DTM_SECTION_RULES.items():
        section = sections.get(key)
        if not section:
            return False, f"{rule['label']} bo'limi yaratilmagan"
        if section.get("custom_html"):
            return False, f"{rule['label']} uchun tayyor HTML ishlatib bo'lmaydi"
        actual = int(section["questions_count"])
        if actual != rule["questions"]:
            return False, f"{rule['label']}: {rule['questions']} ta savol kerak, hozir {actual} ta"
    return True, "ok"


def test_faollik(test_id: int, aktiv: bool) -> bool:
    if aktiv:
        ready, message = dtm_test_tayyorligi(test_id)
        if not ready:
            raise ValueError(message)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE mock_tests SET is_active=%s WHERE id=%s", (aktiv, test_id))
    ok = cur.rowcount > 0
    conn.commit()
    cur.close(); release_connection(conn)
    return ok


def test_ochir(test_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM mock_tests WHERE id=%s", (test_id,))
    ok = cur.rowcount > 0
    conn.commit()
    cur.close(); release_connection(conn)
    return ok


# ─── BO'LIM CRUD ────────────────────────────────────────────────

def section_qosh(test_id: int, section_key: str, label: str,
                  audio_url: str = None, instructions: str = None,
                  sort_order: int = 0) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO mock_test_sections (test_id, section_key, label, audio_url, instructions, sort_order)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (test_id, section_key) DO UPDATE SET
            label = EXCLUDED.label,
            audio_url = EXCLUDED.audio_url,
            instructions = EXCLUDED.instructions,
            sort_order = EXCLUDED.sort_order
        RETURNING id
        """,
        (test_id, section_key, label, audio_url, instructions, sort_order),
    )
    sec_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); release_connection(conn)
    return sec_id


def section_ol(section_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM mock_test_sections WHERE id=%s", (section_id,))
    sec = cur.fetchone()
    cur.close(); release_connection(conn)
    return dict(sec) if sec else None


def section_custom_html_saqla(section_id: int, html: str) -> bool:
    """
    Bo'lim uchun tayyor HTML sahifa (masalan tayyor IELTS Listening varog'i) o'rnatadi.
    Bu o'rnatilgan bo'lsa, talaba shu sahifani ko'radi — qo'lda kiritilgan savollar
    o'rniga. Yangi html yuklanganda eski javob kaliti (custom_answer_key) tozalanadi,
    chunki u eski faylga tegishli edi.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE mock_test_sections SET custom_html=%s, custom_answer_key=NULL WHERE id=%s",
        (html, section_id),
    )
    ok = cur.rowcount > 0
    conn.commit()
    cur.close(); release_connection(conn)
    return ok


def section_custom_html_ochir(section_id: int) -> bool:
    """Tayyor HTML rejimini bekor qiladi — bo'lim qaytadan oddiy savol-javob rejimiga o'tadi."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE mock_test_sections SET custom_html=NULL, custom_answer_key=NULL WHERE id=%s",
        (section_id,),
    )
    ok = cur.rowcount > 0
    conn.commit()
    cur.close(); release_connection(conn)
    return ok


def custom_javob_saqla(attempt_id: int, section_id: int, raw_answers: dict,
                        correct_answers: dict = None, question_types: dict = None,
                        talaba_kod: str = None) -> bool:
    """
    Tayyor HTML sahifadan "ko'prik" skript orqali yig'ilgan xom javoblarni saqlaydi.
    Agar sahifa o'zining javob kalitini (correctAnswers/questionTypes) ham yuborsa va
    bu bo'lim uchun hali hech qachon saqlanmagan bo'lsa, shuni bo'limga bir martalik
    "javob kaliti" sifatida yozib qo'yamiz — shu orqali keyinchalik tekshirish
    sahifasida avtomatik to'g'ri/noto'g'ri belgilash imkoni paydo bo'ladi.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if talaba_kod is not None:
        cur.execute(
            """
            SELECT a.id
            FROM mock_attempts a
            JOIN mock_tests mt ON mt.id=a.test_id
            JOIN mock_test_sections s ON s.test_id=a.test_id AND s.id=%s
            WHERE a.id=%s AND a.talaba_kod=%s AND a.status='in_progress'
              AND a.started_at + mt.duration_minutes * INTERVAL '1 minute' > CURRENT_TIMESTAMP
            """,
            (section_id, attempt_id, talaba_kod),
        )
        if not cur.fetchone():
            cur.close(); release_connection(conn)
            return False

    cur2 = conn.cursor()
    cur2.execute(
        """
        INSERT INTO mock_attempt_custom_answers (attempt_id, section_id, raw_answers)
        VALUES (%s,%s,%s)
        ON CONFLICT (attempt_id, section_id) DO UPDATE SET
            raw_answers = EXCLUDED.raw_answers,
            updated_at = CURRENT_TIMESTAMP
        """,
        (attempt_id, section_id, json.dumps(raw_answers or {})),
    )

    if correct_answers:
        cur.execute(
            "SELECT custom_answer_key FROM mock_test_sections WHERE id=%s",
            (section_id,),
        )
        row = cur.fetchone()
        if row and not row["custom_answer_key"]:
            key = {"correct_answers": correct_answers, "question_types": question_types or {}}
            cur2.execute(
                "UPDATE mock_test_sections SET custom_answer_key=%s WHERE id=%s",
                (json.dumps(key), section_id),
            )

    conn.commit()
    cur.close(); cur2.close(); release_connection(conn)
    return True


def sectionlar_ol(test_id: int) -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM mock_test_sections WHERE test_id=%s ORDER BY sort_order",
        (test_id,),
    )
    rows = cur.fetchall()
    cur.close(); release_connection(conn)
    return [dict(r) for r in rows]


# ─── SAVOL CRUD ─────────────────────────────────────────────────

def savol_qosh(section_id: int, question_type: str, question_text: str,
               content: dict, correct_answer: dict,
               points: float = 1.0, sort_order: int = 0) -> int:
    """
    question_type: 'mcq' | 'matching' | 'fill_blank' | 'true_false'

    content / correct_answer formatlari:

    mcq:
      content = {"options": ["variant A", "variant B", "variant C", "variant D"]}
      correct_answer = {"correct": [0]}        # bir nechta to'g'ri bo'lsa indekslar ro'yxati

    true_false:
      content = {"options": ["True", "False", "Not Given"]}
      correct_answer = {"correct": [1]}

    fill_blank:
      content = {"blanks_count": 3}
      correct_answer = {"answers": [["cat","cats"], ["run"], ["happy","glad"]]}
                        # har bir bo'sh joy uchun qabul qilinadigan variantlar ro'yxati

    matching:
      content = {"items": ["1","2","3"], "options": ["A","B","C","D"]}
      correct_answer = {"map": {"1":"B", "2":"A", "3":"D"}}
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO mock_test_questions
            (section_id, question_type, question_text, content, correct_answer, points, sort_order)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        RETURNING id
        """,
        (section_id, question_type, question_text,
         json.dumps(content), json.dumps(correct_answer), points, sort_order),
    )
    q_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); release_connection(conn)
    return q_id


def savol_yangila(question_id: int, question_text: str = None,
                   content: dict = None, correct_answer: dict = None,
                   points: float = None, sort_order: int = None) -> bool:
    fields, params = [], []
    if question_text is not None:
        fields.append("question_text=%s"); params.append(question_text)
    if content is not None:
        fields.append("content=%s"); params.append(json.dumps(content))
    if correct_answer is not None:
        fields.append("correct_answer=%s"); params.append(json.dumps(correct_answer))
    if points is not None:
        fields.append("points=%s"); params.append(points)
    if sort_order is not None:
        fields.append("sort_order=%s"); params.append(sort_order)
    if not fields:
        return False

    conn = get_connection()
    cur = conn.cursor()
    params.append(question_id)
    cur.execute(f"UPDATE mock_test_questions SET {', '.join(fields)} WHERE id=%s", params)
    ok = cur.rowcount > 0
    conn.commit()
    cur.close(); release_connection(conn)
    return ok


def savollar_ol(section_id: int, include_answers: bool = True) -> list:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM mock_test_questions WHERE section_id=%s ORDER BY sort_order",
        (section_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); release_connection(conn)
    for r in rows:
        if isinstance(r.get("content"), str):
            r["content"] = json.loads(r["content"])
        if isinstance(r.get("correct_answer"), str):
            r["correct_answer"] = json.loads(r["correct_answer"])
        if not include_answers:
            r.pop("correct_answer", None)
    return rows


def savol_ochir(question_id: int) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM mock_test_questions WHERE id=%s", (question_id,))
    ok = cur.rowcount > 0
    conn.commit()
    cur.close(); release_connection(conn)
    return ok


# ─── AVTOMATIK TEKSHIRISH ───────────────────────────────────────

def _javobni_tekshir(question_type: str, student_answer, correct_answer: dict) -> bool:
    """Listening/Reading javoblarini turi bo'yicha avtomatik tekshiradi."""
    try:
        if question_type in ("mcq", "true_false"):
            correct_set = set(correct_answer.get("correct", []))
            if isinstance(student_answer, list):
                student_set = set(student_answer)
            else:
                student_set = {student_answer}
            return student_set == correct_set

        if question_type == "fill_blank":
            accepted = correct_answer.get("answers", [])
            if not isinstance(student_answer, list) or len(student_answer) != len(accepted):
                return False
            for given, options in zip(student_answer, accepted):
                given_norm = str(given).strip().lower()
                options_norm = [str(o).strip().lower() for o in options]
                if given_norm not in options_norm:
                    return False
            return True

        if question_type == "matching":
            correct_map = correct_answer.get("map", {})
            if not isinstance(student_answer, dict):
                return False
            return student_answer == correct_map

        return False
    except Exception:
        return False


def _compare_custom_value(student_val, correct_val):
    """
    Tayyor HTML sahifadan yig'ilgan javobni (masalan q7: 'cats') o'zining
    correctAnswers kalitidagi qiymat bilan solishtiradi. Bunday shablonlarda
    ko'pincha javob yo'q savollar '???' bilan belgilanadi — ularni hisobga
    olmaymiz (None qaytaradi, ya'ni "baholanmagan").
    """
    if correct_val is None or correct_val == "???":
        return None
    accepted = correct_val if isinstance(correct_val, list) else [correct_val]
    if student_val is None or str(student_val).strip() == "":
        return False
    return str(student_val).strip().lower() in [str(a).strip().lower() for a in accepted]


# ─── ATTEMPT (URINISH) ──────────────────────────────────────────

def attempt_boshla(talaba_kod: str, test_id: int) -> int:
    """
    Talaba mockni boshlaganda chaqiriladi. Agar shu testga oid tugallanmagan
    urinish bo'lsa, o'shani qaytaradi (qayta yaratmaydi) — sahifa qayta yuklansa
    ham talaba bir xil urinishda davom etadi.
    """
    test = test_ol(test_id)
    if not test or not test.get("is_active"):
        raise ValueError("Bu test hozir faol emas")
    ready, message = dtm_test_tayyorligi(test_id)
    if not ready:
        raise ValueError(message)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id FROM mock_attempts
        WHERE talaba_kod=%s AND test_id=%s AND status='in_progress'
        ORDER BY started_at DESC LIMIT 1
        """,
        (talaba_kod, test_id),
    )
    row = cur.fetchone()
    if row:
        cur.close(); release_connection(conn)
        return row[0]

    cur.execute(
        "INSERT INTO mock_attempts (talaba_kod, test_id) VALUES (%s,%s) RETURNING id",
        (talaba_kod, test_id),
    )
    attempt_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); release_connection(conn)
    return attempt_id


def javob_saqla(attempt_id: int, question_id: int, student_answer, talaba_kod: str = None) -> bool:
    """
    Listening/Reading javobini saqlaydi va shu zahoti avtomatik tekshiradi.
    talaba_kod berilsa, attempt shu talabaga tegishli ekanligi tekshiriladi
    (ownership) — aks holda False qaytadi va hech narsa saqlanmaydi.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """
        SELECT q.question_type, q.correct_answer
        FROM mock_test_questions q
        JOIN mock_test_sections s ON s.id=q.section_id
        JOIN mock_attempts a ON a.test_id=s.test_id
        JOIN mock_tests mt ON mt.id=a.test_id
        WHERE q.id=%s AND a.id=%s AND a.status='in_progress'
          AND (%s IS NULL OR a.talaba_kod=%s)
          AND a.started_at + mt.duration_minutes * INTERVAL '1 minute' > CURRENT_TIMESTAMP
        """,
        (question_id, attempt_id, talaba_kod, talaba_kod),
    )
    q = cur.fetchone()
    if not q:
        cur.close(); release_connection(conn)
        return False

    correct_answer = q["correct_answer"]
    if isinstance(correct_answer, str):
        correct_answer = json.loads(correct_answer)
    is_correct = _javobni_tekshir(q["question_type"], student_answer, correct_answer)

    cur2 = conn.cursor()
    cur2.execute(
        """
        INSERT INTO mock_attempt_answers (attempt_id, question_id, student_answer, is_correct)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (attempt_id, question_id) DO UPDATE SET
            student_answer = EXCLUDED.student_answer,
            is_correct = EXCLUDED.is_correct,
            answered_at = CURRENT_TIMESTAMP
        """,
        (attempt_id, question_id, json.dumps(student_answer), is_correct),
    )
    conn.commit()
    cur.close(); cur2.close(); release_connection(conn)
    return is_correct


def essay_saqla(attempt_id: int, section_id: int, essay_text: str, talaba_kod: str = None) -> int:
    """Writing inshosini saqlaydi (avtomatik baholanmaydi, admin o'qib chiqadi)."""
    word_count = len(essay_text.split())
    conn = get_connection()

    if talaba_kod is not None:
        cur0 = conn.cursor()
        cur0.execute(
            """
            SELECT a.id
            FROM mock_attempts a
            JOIN mock_tests mt ON mt.id=a.test_id
            JOIN mock_test_sections s ON s.test_id=a.test_id AND s.id=%s
            WHERE a.id=%s AND a.talaba_kod=%s AND a.status='in_progress'
              AND a.started_at + mt.duration_minutes * INTERVAL '1 minute' > CURRENT_TIMESTAMP
            """,
            (section_id, attempt_id, talaba_kod),
        )
        owns = cur0.fetchone()
        cur0.close()
        if not owns:
            release_connection(conn)
            return 0

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO mock_attempt_essays (attempt_id, section_id, essay_text, word_count)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (attempt_id, section_id) DO UPDATE SET
            essay_text = EXCLUDED.essay_text,
            word_count = EXCLUDED.word_count,
            saved_at = CURRENT_TIMESTAMP
        RETURNING id
        """,
        (attempt_id, section_id, essay_text, word_count),
    )
    essay_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); release_connection(conn)
    return essay_id


def attempt_yubor(attempt_id: int, talaba_kod: str = None) -> bool:
    """Talaba mockni yakunlab yuborganda chaqiriladi. Natija hali ko'rsatilmaydi."""
    conn = get_connection()
    cur = conn.cursor()
    if talaba_kod is not None:
        cur.execute(
            """
            UPDATE mock_attempts SET status='submitted', submitted_at=CURRENT_TIMESTAMP
            WHERE id=%s AND talaba_kod=%s AND status='in_progress'
            """,
            (attempt_id, talaba_kod),
        )
    else:
        cur.execute(
            """
            UPDATE mock_attempts SET status='submitted', submitted_at=CURRENT_TIMESTAMP
            WHERE id=%s AND status='in_progress'
            """,
            (attempt_id,),
        )
    ok = cur.rowcount > 0
    conn.commit()
    cur.close(); release_connection(conn)
    return ok


def attempt_holat_ol(attempt_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM mock_attempts WHERE id=%s", (attempt_id,))
    row = cur.fetchone()
    cur.close(); release_connection(conn)
    return dict(row) if row else None


def attempt_meta(attempt_id: int):
    """Natija yakunlash uchun kerakli minimal ma'lumot: talaba_kod, exam_key, status."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT a.id, a.talaba_kod, a.status, a.mock_natija_id, mt.exam_key
        FROM mock_attempts a
        JOIN mock_tests mt ON mt.id = a.test_id
        WHERE a.id=%s
        """,
        (attempt_id,),
    )
    row = cur.fetchone()
    cur.close(); release_connection(conn)
    return dict(row) if row else None


def talaba_attemptlari(talaba_kod: str) -> list:
    """Talabaning barcha urinishlari (status bilan birga)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT a.*, mt.title AS test_title, mt.exam_key,
               mn.umumiy_ball, mn.sections AS result_sections
        FROM mock_attempts a
        JOIN mock_tests mt ON mt.id = a.test_id
        LEFT JOIN mock_natijalari mn ON mn.id = a.mock_natija_id
        WHERE a.talaba_kod=%s
        ORDER BY a.started_at DESC
        """,
        (talaba_kod,),
    )
    rows = cur.fetchall()
    cur.close(); release_connection(conn)
    return [dict(r) for r in rows]


# ─── ADMIN TEKSHIRISH ───────────────────────────────────────────

def tekshirish_kutayotganlar() -> list:
    """Hali tekshirilmagan (status='submitted') barcha urinishlar ro'yxati."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT a.*, t.ismlar, t.sinf, mt.title AS test_title, mt.exam_key
        FROM mock_attempts a
        JOIN talabalar t ON t.kod = a.talaba_kod
        JOIN mock_tests mt ON mt.id = a.test_id
        WHERE a.status='submitted'
        ORDER BY a.submitted_at ASC
        """
    )
    rows = cur.fetchall()
    cur.close(); release_connection(conn)
    return [dict(r) for r in rows]


def attempt_tafsilot(attempt_id: int):
    """
    Admin uchun to'liq tafsilot:
      - Listening/Reading: har bir savol, talaba javobi, to'g'ri javob, to'g'ri/noto'g'ri
      - Writing: insho matni va so'z soni

    Natija ballari hali ko'rsatilmaydi — faqat xom javoblar va matnlar.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """
        SELECT a.*, t.ismlar, t.sinf, mt.title AS test_title, mt.exam_key
        FROM mock_attempts a
        JOIN talabalar t ON t.kod = a.talaba_kod
        JOIN mock_tests mt ON mt.id = a.test_id
        WHERE a.id=%s
        """,
        (attempt_id,),
    )
    attempt = cur.fetchone()
    if not attempt:
        cur.close(); release_connection(conn)
        return None
    attempt = dict(attempt)

    cur.execute(
        """
        SELECT q.id AS question_id, q.question_type, q.question_text,
               q.content, q.correct_answer, q.points,
               s.section_key, s.label AS section_label,
               aa.student_answer, aa.is_correct
        FROM mock_test_questions q
        JOIN mock_test_sections s ON s.id = q.section_id
        LEFT JOIN mock_attempt_answers aa
               ON aa.question_id = q.id AND aa.attempt_id = %s
        WHERE s.test_id = %s AND s.section_key IN ('listening', 'reading')
        ORDER BY s.sort_order, q.sort_order
        """,
        (attempt_id, attempt["test_id"]),
    )
    javoblar = []
    for r in cur.fetchall():
        d = dict(r)
        for key in ("content", "correct_answer", "student_answer"):
            if isinstance(d.get(key), str):
                d[key] = json.loads(d[key])
        javoblar.append(d)
    attempt["listening_reading"] = javoblar
    attempt["listening_reading_summary"] = {
        "jami_savol": len(javoblar),
        "togri_javob": sum(1 for j in javoblar if j["is_correct"]),
    }

    cur.execute(
        """
        SELECT e.*, s.section_key, s.label AS section_label
        FROM mock_attempt_essays e
        JOIN mock_test_sections s ON s.id = e.section_id
        WHERE e.attempt_id=%s
        ORDER BY s.sort_order
        """,
        (attempt_id,),
    )
    attempt["essays"] = [dict(r) for r in cur.fetchall()]

    # Tayyor HTML bo'limlari (custom_html o'rnatilgan bo'limlar)
    cur.execute(
        """
        SELECT s.id AS section_id, s.section_key, s.label AS section_label,
               s.custom_answer_key, ca.raw_answers
        FROM mock_test_sections s
        LEFT JOIN mock_attempt_custom_answers ca
               ON ca.section_id = s.id AND ca.attempt_id = %s
        WHERE s.test_id = %s AND s.custom_html IS NOT NULL
        ORDER BY s.sort_order
        """,
        (attempt_id, attempt["test_id"]),
    )
    custom_sections = []
    for r in cur.fetchall():
        d = dict(r)
        for key in ("custom_answer_key", "raw_answers"):
            if isinstance(d.get(key), str):
                d[key] = json.loads(d[key])
        raw_answers = d.get("raw_answers") or {}
        key_data = d.get("custom_answer_key") or {}
        correct_answers = key_data.get("correct_answers") or {}

        all_keys = sorted(set(list(raw_answers.keys()) + list(correct_answers.keys())))
        rows, correct_count, total_scored = [], 0, 0
        for qk in all_keys:
            student_val = raw_answers.get(qk)
            correct_val = correct_answers.get(qk)
            is_correct = _compare_custom_value(student_val, correct_val)
            if is_correct is not None:
                total_scored += 1
                if is_correct:
                    correct_count += 1
            rows.append({
                "key": qk, "student_answer": student_val,
                "correct_answer": correct_val, "is_correct": is_correct,
            })

        custom_sections.append({
            "section_id": d["section_id"],
            "section_key": d["section_key"],
            "section_label": d["section_label"],
            "rows": rows,
            "has_key": bool(correct_answers),
            "summary": {"jami_savol": total_scored, "togri_javob": correct_count},
        })
    attempt["custom_sections"] = custom_sections

    cur.close(); release_connection(conn)
    return attempt


def attempt_natija_biriktir(attempt_id: int, mock_natija_id: int, admin_id: int) -> bool:
    """
    Admin ballarni `mock_database.mock_natija_qosh()` orqali `mock_natijalari`ga
    kiritib bo'lgandan keyin, shu natija id'sini ushbu attempt'ga bog'laydi va
    statusni 'released' qiladi — shu zahoti talaba odatdagi natija sahifasida
    ko'ra oladi.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE mock_attempts
        SET mock_natija_id=%s, admin_id=%s, status='released', reviewed_at=CURRENT_TIMESTAMP
        WHERE id=%s AND status IN ('submitted', 'reviewed')
        """,
        (mock_natija_id, admin_id, attempt_id),
    )
    ok = cur.rowcount > 0
    conn.commit()
    cur.close(); release_connection(conn)
    return ok


def dtm_attempt_avto_yakunla(attempt_id: int):
    """Yuborilgan DTM urinishini avtomatik hisoblab, natijani darhol e'lon qiladi."""
    meta = attempt_meta(attempt_id)
    if not meta or meta["exam_key"] != DTM_EXAM_KEY:
        return None
    if meta.get("mock_natija_id"):
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT umumiy_ball, sections FROM mock_natijalari WHERE id=%s", (meta["mock_natija_id"],))
        row = cur.fetchone()
        cur.close(); release_connection(conn)
        return dict(row) if row else None
    if meta["status"] != "submitted":
        return None

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT s.section_key, COUNT(q.id) AS questions_count,
               COUNT(q.id) FILTER (WHERE aa.is_correct=TRUE) AS correct_count
        FROM mock_test_sections s
        LEFT JOIN mock_test_questions q ON q.section_id=s.id
        LEFT JOIN mock_attempt_answers aa
               ON aa.question_id=q.id AND aa.attempt_id=%s
        JOIN mock_attempts a ON a.id=%s AND a.test_id=s.test_id
        GROUP BY s.id
        """,
        (attempt_id, attempt_id),
    )
    rows = {r["section_key"]: dict(r) for r in cur.fetchall()}
    cur.close(); release_connection(conn)

    counts = {}
    for key, rule in DTM_SECTION_RULES.items():
        row = rows.get(key)
        actual = int(row["questions_count"]) if row else 0
        if actual != rule["questions"]:
            raise ValueError(f"{rule['label']}: {rule['questions']} ta savol bo'lishi kerak")
        counts[key] = int(row["correct_count"] or 0)

    sections = dtm_sections_natijasi(counts)
    total = dtm_ball_hisobla(counts)
    from mock_database import mock_natija_qosh
    natija_id = mock_natija_qosh(
        talaba_kod=meta["talaba_kod"],
        exam_key=DTM_EXAM_KEY,
        sections=sections,
        umumiy_ball=total,
        notes="Avtomatik hisoblangan DTM simulator natijasi",
    )
    if not attempt_natija_biriktir(attempt_id, natija_id, admin_id=None):
        raise RuntimeError("DTM natijasini urinishga biriktirib bo'lmadi")
    return {"natija_id": natija_id, "umumiy_ball": total, "sections": sections}


# ─────────────────────────────────────────────────────────────────
# TALABA TOMONI — login sessiyasi
# ─────────────────────────────────────────────────────────────────
#
# Talaba saytga to'g'ridan-to'g'ri o'z kodi bilan kiradi (Telegram orqali
# emas). Xavfsizlik uchun kod faqat bir martalik login'da ishlatiladi —
# tekshirilgandan keyin server tasodifiy token (sessiya) yaratadi va shu
# tokenni httpOnly cookie orqali talabaga beradi. Keyingi barcha so'rovlar
# (javob saqlash, mock yuborish) faqat shu tokendan kelib chiqadi, talaba
# o'zi yubormagan kodga ega bo'la olmaydi.

def talaba_login(kod: str):
    """
    Kodni tekshiradi, to'g'ri bo'lsa yangi sessiya yaratadi.
    Qaytaradi: (token, talaba_dict) yoki (None, None) agar kod topilmasa/aktiv bo'lmasa.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT kod, ismlar, sinf, yonalish FROM talabalar WHERE kod=%s AND status='aktiv'",
        (kod.strip().upper(),),
    )
    talaba = cur.fetchone()
    if not talaba:
        cur.close(); release_connection(conn)
        return None, None

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=6)
    cur2 = conn.cursor()
    cur2.execute(
        "INSERT INTO mock_web_sessions (token, talaba_kod, expires_at) VALUES (%s,%s,%s)",
        (token, talaba["kod"], expires_at),
    )
    conn.commit()
    cur.close(); cur2.close(); release_connection(conn)
    return token, dict(talaba)


def session_talaba_kod(token: str):
    """Token haqiqiy va muddati o'tmaganligini tekshirib, talaba kodini qaytaradi."""
    if not token:
        return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT talaba_kod FROM mock_web_sessions WHERE token=%s AND expires_at > CURRENT_TIMESTAMP",
        (token,),
    )
    row = cur.fetchone()
    cur.close(); release_connection(conn)
    return row[0] if row else None


def session_ochir(token: str) -> None:
    """Logout — sessiyani o'chiradi."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM mock_web_sessions WHERE token=%s", (token,))
    conn.commit()
    cur.close(); release_connection(conn)


def eski_sessiyalarni_tozala() -> int:
    """Muddati o'tgan sessiyalarni o'chiradi (vaqti-vaqti bilan chaqirish mumkin)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM mock_web_sessions WHERE expires_at <= CURRENT_TIMESTAMP")
    n = cur.rowcount
    conn.commit()
    cur.close(); release_connection(conn)
    return n


# ─────────────────────────────────────────────────────────────────
# TALABA TOMONI — mock topshirish uchun ma'lumot olish
# ─────────────────────────────────────────────────────────────────

def talaba_uchun_testlar(exam_key: str = None) -> list:
    """Talabaga ko'rsatiladigan aktiv testlar ro'yxati (bo'limlar soni bilan)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sql = """
        SELECT mt.id, mt.exam_key, mt.title, mt.duration_minutes,
               COUNT(ms.id) AS sections_count
        FROM mock_tests mt
        LEFT JOIN mock_test_sections ms ON ms.test_id = mt.id
        WHERE mt.is_active = TRUE
    """
    params = []
    if exam_key:
        sql += " AND mt.exam_key=%s"
        params.append(exam_key)
    sql += " GROUP BY mt.id ORDER BY mt.created_at DESC"
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close(); release_connection(conn)
    result = []
    for row in rows:
        item = dict(row)
        ready, _ = dtm_test_tayyorligi(item["id"])
        if ready:
            result.append(item)
    return result


def attempt_umumiy_holat(attempt_id: int, talaba_kod: str):
    """
    Talabaning urinishi haqida umumiy ma'lumot: test, bo'limlar (savol/javob soni),
    qolgan vaqt. Faqat shu attempt talaba kodiga tegishli bo'lsagina qaytaradi
    (ownership tekshiruvi — boshqa talabaning urinishini ko'ra olmaydi).
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT a.*, mt.title AS test_title, mt.exam_key, mt.duration_minutes
        FROM mock_attempts a
        JOIN mock_tests mt ON mt.id = a.test_id
        WHERE a.id=%s AND a.talaba_kod=%s
        """,
        (attempt_id, talaba_kod),
    )
    attempt = cur.fetchone()
    if not attempt:
        cur.close(); release_connection(conn)
        return None
    attempt = dict(attempt)

    cur.execute(
        """
        SELECT s.id, s.section_key, s.label, s.audio_url, s.instructions, s.sort_order,
               COUNT(q.id) AS questions_count,
               COUNT(aa.id) AS answered_count
        FROM mock_test_sections s
        LEFT JOIN mock_test_questions q ON q.section_id = s.id
        LEFT JOIN mock_attempt_answers aa ON aa.question_id = q.id AND aa.attempt_id = %s
        WHERE s.test_id = %s
        GROUP BY s.id
        ORDER BY s.sort_order
        """,
        (attempt_id, attempt["test_id"]),
    )
    attempt["sections"] = [dict(r) for r in cur.fetchall()]

    elapsed = (datetime.now() - attempt["started_at"]).total_seconds()
    remaining = attempt["duration_minutes"] * 60 - elapsed
    attempt["remaining_seconds"] = max(0, int(remaining))

    cur.close(); release_connection(conn)
    return attempt


def section_savollari_talabaga(attempt_id: int, section_id: int, talaba_kod: str):
    """
    Bitta bo'lim savollari, talabaning oldin saqlagan javoblari bilan (agar bor bo'lsa),
    LEKIN to'g'ri javob (correct_answer) va is_correct hech qachon qaytarilmaydi.
    Writing bo'limi bo'lsa, savol o'rniga saqlangan insho matni qaytariladi.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """
        SELECT s.*
        FROM mock_test_sections s
        JOIN mock_attempts a ON a.test_id=s.test_id
        WHERE s.id=%s AND a.id=%s AND a.talaba_kod=%s AND a.status='in_progress'
        """,
        (section_id, attempt_id, talaba_kod),
    )
    section = cur.fetchone()
    if not section:
        cur.close(); release_connection(conn)
        return None
    section = dict(section)
    section.pop("custom_answer_key", None)

    if section.get("custom_html"):
        cur.execute(
            "SELECT raw_answers FROM mock_attempt_custom_answers WHERE attempt_id=%s AND section_id=%s",
            (attempt_id, section_id),
        )
        existing = cur.fetchone()
        section["is_custom"] = True
        raw = (existing["raw_answers"] if existing else {}) or {}
        if isinstance(raw, str):
            raw = json.loads(raw)
        section["raw_answers"] = raw
        cur.close(); release_connection(conn)
        return section

    if section["section_key"] == "writing":
        cur.execute(
            "SELECT essay_text, word_count FROM mock_attempt_essays WHERE attempt_id=%s AND section_id=%s",
            (attempt_id, section_id),
        )
        existing = cur.fetchone()
        section["essay_text"] = existing["essay_text"] if existing else ""
        section["word_count"] = existing["word_count"] if existing else 0
        cur.close(); release_connection(conn)
        return section

    cur.execute(
        """
        SELECT q.id AS question_id, q.question_type, q.question_text, q.content, q.points,
               aa.student_answer
        FROM mock_test_questions q
        LEFT JOIN mock_attempt_answers aa
               ON aa.question_id = q.id AND aa.attempt_id = %s
        WHERE q.section_id = %s
        ORDER BY q.sort_order
        """,
        (attempt_id, section_id),
    )
    questions = []
    for r in cur.fetchall():
        d = dict(r)
        for key in ("content", "student_answer"):
            if isinstance(d.get(key), str):
                d[key] = json.loads(d[key])
        questions.append(d)
    section["questions"] = questions

    cur.close(); release_connection(conn)
    return section
