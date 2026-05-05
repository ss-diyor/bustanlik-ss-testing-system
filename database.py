import psycopg2
import psycopg2.extras
from psycopg2 import pool
import os
import json
import logging
from config import MAJBURIY_KOEFF, ASOSIY_1_KOEFF, ASOSIY_2_KOEFF

DATABASE_URL = os.getenv("DATABASE_URL")


# Admin sessiyalari jadvali
def create_admin_sessions_table():
    """Admin sessiyalari jadvalini yaratish"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_sessions (
            id SERIAL PRIMARY KEY,
            admin_id BIGINT NOT NULL,
            admin_name VARCHAR(100) NOT NULL,
            login_time TIMESTAMP NOT NULL DEFAULT NOW(),
            logout_time TIMESTAMP,
            is_active BOOLEAN NOT NULL DEFAULT true
        )
    """)
    conn.commit()
    cur.close()
    release_connection(conn)

def create_mini_test_tables():
    """Mini-testlar uchun jadvallarni yaratish"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mini_testlar (
            id SERIAL PRIMARY KEY,
            nomi VARCHAR(255) NOT NULL DEFAULT 'Mini-test',
            fan VARCHAR(100) NOT NULL,
            pdf_file_id VARCHAR(255),
            keys JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            admin_id BIGINT
        )
    """)
    # Migration: Ensure required columns exist in mini_testlar
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'mini_testlar' AND column_name = 'nomi') THEN
                ALTER TABLE mini_testlar ADD COLUMN nomi VARCHAR(255) NOT NULL DEFAULT 'Mini-test';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'mini_testlar' AND column_name = 'fan') THEN
                ALTER TABLE mini_testlar ADD COLUMN fan VARCHAR(100) NOT NULL DEFAULT 'Umumiy';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'mini_testlar' AND column_name = 'pdf_file_id') THEN
                ALTER TABLE mini_testlar ADD COLUMN pdf_file_id VARCHAR(255);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'mini_testlar' AND column_name = 'keys') THEN
                ALTER TABLE mini_testlar ADD COLUMN keys JSONB NOT NULL DEFAULT '{}';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'mini_testlar' AND column_name = 'is_active') THEN
                ALTER TABLE mini_testlar ADD COLUMN is_active BOOLEAN DEFAULT TRUE;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'mini_testlar' AND column_name = 'admin_id') THEN
                ALTER TABLE mini_testlar ADD COLUMN admin_id BIGINT;
            END IF;
        END $$;
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mini_test_natijalari (
            id SERIAL PRIMARY KEY,
            test_id INTEGER REFERENCES mini_testlar(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL,
            talaba_kod VARCHAR(50),
            ball FLOAT,
            jami_savol INTEGER,
            sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    release_connection(conn)


# Connection pool — lazy yaratiladi (birinchi so'rovda)
# Bu Railway cold start muammosini hal qiladi
connection_pool = None


def _get_pool():
    global connection_pool
    if connection_pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        import time

        for attempt in range(5):
            try:
                # sslmode faqat DATABASE_URL da ko'rsatilmagan bo'lsa qo'shamiz
                # Railway DATABASE_URL allaqachon sslmode=require o'z ichiga olgan bo'lishi mumkin
                extra_kwargs = {}
                if "sslmode" not in DATABASE_URL:
                    extra_kwargs["sslmode"] = "require"
                connection_pool = pool.SimpleConnectionPool(
                    1, 10, DATABASE_URL, connect_timeout=10, **extra_kwargs
                )
                logging.info("Connection pool created successfully")
                break
            except Exception as e:
                logging.warning(
                    "Pool creation attempt %s/5 failed: %s", attempt + 1, e
                )
                time.sleep(3)
        if connection_pool is None:
            raise Exception("Failed to connect to PostgreSQL")
    return connection_pool


def get_connection():
    try:
        conn = _get_pool().getconn()
        # Ulanish hali ham tirik ekanligini tekshiramiz
        conn.cursor().execute("SELECT 1")
        return conn
    except Exception:
        # Pool buzilgan bo'lsa, yangisini yaratamiz
        global connection_pool
        connection_pool = None
        return _get_pool().getconn()


def release_connection(conn):
    try:
        _get_pool().putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


def init_db():
    conn = get_connection()
    cur = conn.cursor()
    sp_idx = 0

    def _optional_exec(sql: str, params=None):
        """Xato bo'lsa ham umumiy transactionni buzmasdan davom etish."""
        nonlocal sp_idx
        sp_name = f"sp_opt_{sp_idx}"
        sp_idx += 1
        cur.execute(f"SAVEPOINT {sp_name}")
        try:
            if params is None:
                cur.execute(sql)
            else:
                cur.execute(sql, params)
        except Exception:
            cur.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
        finally:
            cur.execute(f"RELEASE SAVEPOINT {sp_name}")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS talabalar (
            id SERIAL PRIMARY KEY,
            kod TEXT UNIQUE NOT NULL,
            yonalish TEXT NOT NULL,
            sinf TEXT,
            ismlar TEXT,
            user_id BIGINT DEFAULT NULL,
            status TEXT DEFAULT 'aktiv',
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Index qo'shish (qidiruvni tezlashtirish uchun)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_talabalar_kod ON talabalar(kod)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_talabalar_user_id ON talabalar(user_id)"
    )
    # Migration: blockchain hash ustuni (IF NOT EXISTS — xavfsiz)
    cur.execute(
        "ALTER TABLE talabalar ADD COLUMN IF NOT EXISTS cert_hash TEXT DEFAULT NULL"
    )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS test_natijalari (
            id SERIAL PRIMARY KEY,
            talaba_kod TEXT NOT NULL,
            majburiy INTEGER NOT NULL,
            asosiy_1 INTEGER NOT NULL,
            asosiy_2 INTEGER NOT NULL,
            umumiy_ball REAL NOT NULL,
            test_sanasi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (talaba_kod) REFERENCES talabalar (kod) ON DELETE CASCADE
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_test_natijalari_kod ON test_natijalari(talaba_kod)"
    )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Eski foydalanuvchilarga phone_number ustunini qo'shish
    _optional_exec(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number TEXT"
    )
    # Multi-language uchun til ustunini qo'shamiz
    _optional_exec(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'uz'"
    )
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_notification_settings (
            user_id BIGINT PRIMARY KEY,
            notify_results BOOLEAN NOT NULL DEFAULT TRUE,
            notify_mock_results BOOLEAN NOT NULL DEFAULT TRUE,
            notify_admin_messages BOOLEAN NOT NULL DEFAULT TRUE,
            notify_reminders BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS yonalishlar (
            id SERIAL PRIMARY KEY,
            nomi TEXT UNIQUE NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sinflar (
            id SERIAL PRIMARY KEY,
            nomi TEXT NOT NULL,
            maktab_id INTEGER DEFAULT 1,
            UNIQUE (nomi, maktab_id)
        )
    """)
    # Eski sxemalarda sinf nomi global UNIQUE bo'lib qolgan bo'lishi mumkin.
    # Bu holda turli maktablarda bir xil sinf nomini (masalan 11-A) qo'shib bo'lmaydi.
    # Quyidagi migratsiya global UNIQUE cheklovlarni olib tashlaydi va composite UNIQUE ni saqlab qoladi.
    _optional_exec("""
            DO $$
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN
                    SELECT c.conname
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    WHERE t.relname = 'sinflar'
                      AND c.contype = 'u'
                      AND pg_get_constraintdef(c.oid) ILIKE 'UNIQUE (nomi)%'
                      AND pg_get_constraintdef(c.oid) NOT ILIKE 'UNIQUE (nomi, maktab_id)%'
                LOOP
                    EXECUTE format('ALTER TABLE sinflar DROP CONSTRAINT IF EXISTS %I', r.conname);
                END LOOP;
            END $$;
        """)
    _optional_exec(
        """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_sinflar_nomi_maktab
            ON sinflar (nomi, maktab_id)
            """
    )

    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS access_requests (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            talaba_kod TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP DEFAULT NULL,
            FOREIGN KEY (talaba_kod) REFERENCES talabalar (kod)
        )
    """)
    # Eski bazalarda expires_at ustuni bo'lmasligi mumkin, uni qo'shib qo'yamiz
    _optional_exec(
        "ALTER TABLE access_requests ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP DEFAULT NULL"
    )

    # Eski bazalarda status ustuni bo'lmasligi mumkin, uni qo'shib qo'yamiz
    _optional_exec(
        "ALTER TABLE talabalar ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'aktiv'"
    )

    # Default settings
    cur.execute(
        "INSERT INTO settings (key, value) VALUES ('ranking_enabled', 'True') ON CONFLICT DO NOTHING"
    )
    cur.execute(
        "INSERT INTO settings (key, value) VALUES ('stats_enabled', 'True') ON CONFLICT DO NOTHING"
    )
    cur.execute(
        "INSERT INTO settings (key, value) VALUES ('chatbot_enabled', 'True') ON CONFLICT DO NOTHING"
    )
    
    # Mini-testlar
    create_mini_test_tables()
    cur.execute(
        "INSERT INTO settings (key, value) VALUES ('mock_enabled', 'True') ON CONFLICT DO NOTHING"
    )

    # ── Sertifikat sozlamalari (default) ─────────────────────────────────────
    _cert_defaults = [
        ("cert_sarlavha",    "SERTIFIKAT"),
        ("cert_subtitle",    "O'quvchining ismi va familyasi"),
        ("cert_maktab_nomi", "Bo'stonliq tumani ixtisoslashtirilgan maktabining"),
        ("cert_matn",        "Bustanlik SS Testing System DTM imtihonida olingan ball"),
        ("cert_rang_r",      "0"),
        ("cert_rang_g",      "0"),
        ("cert_rang_b",      "128"),
        ("cert_logo_path",   ""),
    ]
    for _key, _val in _cert_defaults:
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (_key, _val),
        )
    # ─────────────────────────────────────────────────────────────────────────

    cur.execute("""
        CREATE TABLE IF NOT EXISTS test_kalitlari (
            id SERIAL PRIMARY KEY,
            test_nomi TEXT UNIQUE NOT NULL,
            yonalish TEXT DEFAULT NULL,
            kalitlar TEXT NOT NULL,
            holat TEXT DEFAULT 'ochiq',
            yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS oqituvchilar (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            ismlar TEXT,
            sinf TEXT,
            maktab_id INTEGER DEFAULT 1,
            yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS test_taqvimi (
            id SERIAL PRIMARY KEY,
            test_nomi TEXT NOT NULL,
            sana DATE NOT NULL,
            vaqt TEXT,
            sinf TEXT DEFAULT 'Barchaga',
            yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS materiallar (
            id SERIAL PRIMARY KEY,
            nomi TEXT NOT NULL,
            turi TEXT DEFAULT 'pdf', -- pdf, video, link
            link TEXT NOT NULL,
            fanni_nomi TEXT,
            sinf TEXT DEFAULT 'Barchaga',
            yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS practice_questions (
            id SERIAL PRIMARY KEY,
            subject TEXT NOT NULL,
            question TEXT NOT NULL,
            options JSONB NOT NULL,
            correct_option INTEGER NOT NULL,
            explanation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS maktablar (
            id SERIAL PRIMARY KEY,
            nomi TEXT UNIQUE NOT NULL,
            yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Maktablar jadvalini tekshirish va 'Bo'stonliq ITMA' ni yaratish/yangilash
    cur.execute(
        "SELECT id FROM maktablar WHERE nomi = 'Asosiy maktab' OR nomi = 'Bo''stonliq ITMA' LIMIT 1"
    )
    row = cur.fetchone()
    if row:
        maktab_id = row[0]
        cur.execute(
            "UPDATE maktablar SET nomi = 'Bo''stonliq ITMA' WHERE id = %s",
            (maktab_id,),
        )
    else:
        cur.execute(
            "INSERT INTO maktablar (nomi) VALUES ('Bo''stonliq ITMA') RETURNING id"
        )
        maktab_id = cur.fetchone()[0]

    # Barcha mavjud sinflarni ushbu maktabga biriktirish:
    # 1) maktab_id IS NULL bo'lganlar
    # 2) maktab_id si maktablar jadvalida mavjud bo'lmaganlar ("yetim" sinflar) — asosiy bug fix
    _optional_exec(
        "UPDATE sinflar SET maktab_id = %s WHERE maktab_id IS NULL",
        (maktab_id,),
    )
    _optional_exec(
        """
            UPDATE sinflar SET maktab_id = %s
            WHERE maktab_id NOT IN (SELECT id FROM maktablar)
        """,
        (maktab_id,),
    )

    # Mavjud talabalarning sinf nomini yangilash (agar formatga tushmasa)
    _optional_exec("""
            UPDATE talabalar 
            SET sinf = sinf || ' - Bo''stonliq ITMA' 
            WHERE sinf IS NOT NULL AND sinf NOT LIKE '% - %'
        """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id SERIAL PRIMARY KEY,
            xabar TEXT NOT NULL,
            yuborish_vaqti TIMESTAMP NOT NULL,
            holat TEXT DEFAULT 'kutilmoqda',
            yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS guruhlar (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT UNIQUE NOT NULL,
            nomi TEXT,
            yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS appeals (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            talaba_kod TEXT NOT NULL,
            xabar TEXT NOT NULL,
            javob TEXT DEFAULT NULL,
            status TEXT DEFAULT 'kutilmoqda',
            yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (talaba_kod) REFERENCES talabalar (kod)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ai_usage_logs (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_created_at ON ai_usage_logs(created_at)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_usage_logs_user_id ON ai_usage_logs(user_id)"
    )

    # Mavjud jadvallarga maktab_id qo'shish
    tables_to_update = [
        "talabalar",
        "yonalishlar",
        "sinflar",
        "test_kalitlari",
    ]
    for table in tables_to_update:
        _optional_exec(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS maktab_id INTEGER DEFAULT 1"
        )

    cur.execute("SELECT COUNT(*) FROM yonalishlar")
    if cur.fetchone()[0] == 0:
        boshlangich_yonalish = [
            "Matematika + Fizika",
            "Matematika + Ingliz tili",
            "Matematika + Kimyo",
            "Matematika + Informatika",
            "Ingliz tili + Ona tili",
            "Ingliz tili + Tarix",
            "Biologiya + Kimyo",
            "Tarix + Geografiya",
        ]
        cur.executemany(
            "INSERT INTO yonalishlar (nomi) VALUES (%s) ON CONFLICT DO NOTHING",
            [(y,) for y in boshlangich_yonalish],
        )

    cur.execute("SELECT COUNT(*) FROM sinflar")
    if cur.fetchone()[0] == 0:
        boshlangich_sinflar = ["11-A", "11-B", "10-A", "10-B", "9-A", "9-B"]
        cur.executemany(
            "INSERT INTO sinflar (nomi) VALUES (%s) ON CONFLICT DO NOTHING",
            [(s,) for s in boshlangich_sinflar],
        )

    conn.commit()
    cur.close()
    release_connection(conn)


def yonalish_ol():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT nomi FROM yonalishlar ORDER BY nomi ASC")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [r["nomi"] for r in rows]


def yonalish_qosh(nomi: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO yonalishlar (nomi) VALUES (%s)", (nomi,))
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False


def yonalish_ochir(nomi: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM yonalishlar WHERE nomi = %s", (nomi,))
    conn.commit()
    cur.close()
    release_connection(conn)


def sinf_ol():
    """
    Barcha sinflarni qaytaradi.
    LEFT JOIN ishlatiladi — maktab_id to'g'ri bo'lmasa ham sinf ko'rinadi.
    Qaytariladi: ["11-A - Bo'stonliq ITMA", ...]
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT s.id, s.nomi AS sinf_nomi, 
               COALESCE(m.nomi, 'Noma''lum maktab') AS maktab_nomi
        FROM sinflar s
        LEFT JOIN maktablar m ON s.maktab_id = m.id
        ORDER BY maktab_nomi ASC, s.nomi ASC
    """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [f"{r['sinf_nomi']} - {r['maktab_nomi']}" for r in rows]


def sinf_ol_batafsil():
    """
    Barcha sinflarni to'liq ma'lumot bilan qaytaradi.
    Qaytariladi: [{"id": 1, "nomi": "11-A", "maktab_id": 2, "maktab_nomi": "..."}, ...]
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT s.id, s.nomi, s.maktab_id,
               COALESCE(m.nomi, 'Noma''lum maktab') AS maktab_nomi
        FROM sinflar s
        LEFT JOIN maktablar m ON s.maktab_id = m.id
        ORDER BY maktab_nomi ASC, s.nomi ASC
    """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def sinf_qosh(nomi: str, maktab_id: int) -> bool:
    """Yangi sinf qo'shadi. maktab_id majburiy."""
    try:
        clean_name = " ".join((nomi or "").strip().split())
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sinflar (nomi, maktab_id)
            VALUES (%s, %s)
            ON CONFLICT (nomi, maktab_id) DO NOTHING
        """,
            (clean_name, maktab_id),
        )
        inserted = cur.rowcount > 0
        conn.commit()
        cur.close()
        release_connection(conn)
        return inserted
    except Exception:
        return False


def sinf_ochir(full_name: str):
    """Nom bo'yicha o'chirish (meros — ishlatilmaydi). sinf_ochir_id ishlatish tavsiya etiladi."""
    try:
        parts = full_name.split(" - ", 1)
        sinf_nomi = parts[0]
        maktab_nomi = parts[1] if len(parts) > 1 else None
        conn = get_connection()
        cur = conn.cursor()
        if maktab_nomi:
            cur.execute(
                """
                DELETE FROM sinflar
                WHERE nomi = %s AND maktab_id = (SELECT id FROM maktablar WHERE nomi = %s LIMIT 1)
            """,
                (sinf_nomi, maktab_nomi),
            )
        else:
            cur.execute("DELETE FROM sinflar WHERE nomi = %s", (sinf_nomi,))
        conn.commit()
        cur.close()
        release_connection(conn)
    except Exception:
        pass


def sinf_ochir_id(sinf_id: int) -> bool:
    """Sinf ID bo'yicha o'chiradi. Xavfsiz va aniq."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM sinflar WHERE id = %s", (sinf_id,))
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False


def sinf_talabalar_soni(sinf_id: int) -> int:
    """Sinfga tegishli o'quvchilar sonini qaytaradi (o'chirishdan oldin tekshirish uchun)."""
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Sinf nomini olamiz
        cur.execute(
            "SELECT s.nomi, COALESCE(m.nomi,'') AS maktab_nomi FROM sinflar s LEFT JOIN maktablar m ON s.maktab_id=m.id WHERE s.id=%s",
            (sinf_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            release_connection(conn)
            return 0
        full_name = (
            f"{row['nomi']} - {row['maktab_nomi']}"
            if row["maktab_nomi"]
            else row["nomi"]
        )
        cur.execute(
            "SELECT COUNT(*) FROM talabalar WHERE sinf = %s", (full_name,)
        )
        count = cur.fetchone()[0]
        cur.close()
        release_connection(conn)
        return count
    except Exception:
        return 0


def sinf_id_dan_full_nomi(sinf_id: int) -> str | None:
    """Sinf ID dan to'liq nom qaytaradi: '11-A - Bo'stonliq ITMA'"""
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT s.nomi, COALESCE(m.nomi, 'Noma''lum maktab') AS maktab_nomi
            FROM sinflar s
            LEFT JOIN maktablar m ON s.maktab_id = m.id
            WHERE s.id = %s
        """,
            (sinf_id,),
        )
        row = cur.fetchone()
        cur.close()
        release_connection(conn)
        if row:
            return f"{row['nomi']} - {row['maktab_nomi']}"
        return None
    except Exception:
        return None


def kalit_qosh(test_nomi: str, kalitlar: str, yonalish: str = None) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO test_kalitlari (test_nomi, yonalish, kalitlar) VALUES (%s, %s, %s)",
            (test_nomi, yonalish, kalitlar.upper()),
        )
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False


def kalit_ol(test_nomi: str = None, yonalish: str = None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if test_nomi:
        cur.execute(
            "SELECT * FROM test_kalitlari WHERE test_nomi = %s", (test_nomi,)
        )
        row = cur.fetchone()
        cur.close()
        release_connection(conn)
        return dict(row) if row else None
    elif yonalish:
        cur.execute(
            "SELECT * FROM test_kalitlari WHERE yonalish = %s OR yonalish IS NULL ORDER BY yaratilgan_sana DESC",
            (yonalish,),
        )
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return [dict(r) for r in rows]
    else:
        cur.execute(
            "SELECT * FROM test_kalitlari ORDER BY yaratilgan_sana DESC"
        )
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return [dict(r) for r in rows]


def kalit_tahrirla(test_nomi: str, yangi_kalitlar: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE test_kalitlari SET kalitlar = %s WHERE test_nomi = %s",
        (yangi_kalitlar.upper(), test_nomi),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def kalit_holat_ozgartir(test_nomi: str, holat: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE test_kalitlari SET holat = %s WHERE test_nomi = %s",
        (holat, test_nomi),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def kalit_ochir(test_nomi: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM test_kalitlari WHERE test_nomi = %s", (test_nomi,)
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def ball_hisobla(majburiy: int, asosiy_1: int, asosiy_2: int) -> float:
    ball = (
        majburiy * MAJBURIY_KOEFF
        + asosiy_1 * ASOSIY_1_KOEFF
        + asosiy_2 * ASOSIY_2_KOEFF
    )
    return round(ball, 2)


def talaba_qosh(
    kod: str,
    yonalish: str,
    sinf: str = None,
    ismlar: str = None,
    maktab_id: int = None,
) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO talabalar (kod, yonalish, sinf, ismlar, maktab_id)
            VALUES (%s, %s, %s, %s, COALESCE(%s, 1))
        """,
            (kod.upper(), yonalish, sinf, ismlar, maktab_id),
        )
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False


def natija_qosh(
    talaba_kod: str, majburiy: int, asosiy_1: int, asosiy_2: int
) -> bool:
    ball = ball_hisobla(majburiy, asosiy_1, asosiy_2)
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO test_natijalari (talaba_kod, majburiy, asosiy_1, asosiy_2, umumiy_ball)
            VALUES (%s, %s, %s, %s, %s)
        """,
            (talaba_kod.upper(), majburiy, asosiy_1, asosiy_2, ball),
        )
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False


def talaba_topish(kod: str):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM talabalar WHERE kod = %s", (kod.upper(),))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    finally:
        release_connection(conn)


def talaba_topish_user_id(user_id: int):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM talabalar WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    finally:
        release_connection(conn)


def talaba_ochir(kod: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Avval bog'liq ma'lumotlarni o'chiramiz
        cur.execute(
            "DELETE FROM access_requests WHERE talaba_kod = %s", (kod.upper(),)
        )
        cur.execute(
            "DELETE FROM test_natijalari WHERE talaba_kod = %s", (kod.upper(),)
        )
        cur.execute(
            "DELETE FROM appeals WHERE talaba_kod = %s", (kod.upper(),)
        )
        # Keyin talabaning o'zini
        cur.execute("DELETE FROM talabalar WHERE kod = %s", (kod.upper(),))
        conn.commit()
        cur.close()
        return True
    except Exception:
        return False
    finally:
        release_connection(conn)


def talaba_natijalari(kod: str, limit: int = None):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query = "SELECT * FROM test_natijalari WHERE talaba_kod = %s ORDER BY test_sanasi DESC"
        if limit:
            query += f" LIMIT {limit}"
        cur.execute(query, (kod.upper(),))
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]
    finally:
        release_connection(conn)


def talaba_songi_natija(kod: str):
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT * FROM test_natijalari
            WHERE talaba_kod = %s
            ORDER BY test_sanasi DESC LIMIT 1
        """,
            (kod.upper(),),
        )
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None
    finally:
        release_connection(conn)


def oqituvchi_qosh(user_id: int, ismlar: str, sinf: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO oqituvchilar (user_id, ismlar, sinf)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET ismlar = EXCLUDED.ismlar, sinf = EXCLUDED.sinf
        """,
            (user_id, ismlar, sinf),
        )
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False


def oqituvchi_ol(user_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM oqituvchilar WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return dict(row) if row else None


def oqituvchilar_hammasi():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM oqituvchilar ORDER BY ismlar ASC")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def oqituvchi_ochir(user_id: int) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM oqituvchilar WHERE user_id = %s", (user_id,))
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False


def talaba_user_id_ol(kod: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT user_id FROM talabalar WHERE kod = %s", (kod.upper(),))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return row["user_id"] if row else None


def talaba_user_id_yangila(kod: str, user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE talabalar SET user_id = %s WHERE kod = %s",
        (user_id, kod.upper()),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def get_all_students():
    """Barcha o'quvchilar ro'yxatini qaytarish (faqat asosiy ma'lumotlar)"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT kod, ismlar, sinf, yonalish, status
        FROM talabalar
        WHERE status != 'arxiv'
        ORDER BY sinf ASC, ismlar ASC
    """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return rows


def get_all_students_for_excel():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.kod, t.sinf, t.yonalish, t.ismlar,
               n.majburiy, n.asosiy_1, n.asosiy_2, n.umumiy_ball, n.test_sanasi
        FROM talabalar t
        LEFT JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        ORDER BY t.sinf ASC, n.umumiy_ball DESC NULLS LAST
    """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_sorted_students_for_excel():
    """Barcha o'quvchilarni ballari bo'yicha kamayish tartibida (reyting) oladi."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.kod, t.sinf, t.yonalish, t.ismlar,
               n.majburiy, n.asosiy_1, n.asosiy_2, n.umumiy_ball, n.test_sanasi
        FROM talabalar t
        LEFT JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        WHERE n.umumiy_ball IS NOT NULL
        ORDER BY n.umumiy_ball DESC
    """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_sorted_students_for_excel_by_maktab(maktab_id: int):
    """Maktab bo'yicha o'quvchilarni ballari bo'yicha kamayish tartibida (reyting) oladi."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.kod, t.sinf, t.yonalish, t.ismlar,
               n.majburiy, n.asosiy_1, n.asosiy_2, n.umumiy_ball, n.test_sanasi
        FROM talabalar t
        LEFT JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        WHERE t.maktab_id = %s AND n.umumiy_ball IS NOT NULL
        ORDER BY n.umumiy_ball DESC
    """, (maktab_id,))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def talaba_hammasi():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.*, n.umumiy_ball
        FROM talabalar t
        LEFT JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        ORDER BY t.sinf ASC, n.umumiy_ball DESC NULLS LAST
    """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def talaba_hammasi_by_maktab(maktab_id: int):
    """Maktab bo'yicha barcha talabalarni olish"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.*, n.umumiy_ball
        FROM talabalar t
        LEFT JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        WHERE t.maktab_id = %s
        ORDER BY t.sinf ASC, n.umumiy_ball DESC NULLS LAST
    """, (maktab_id,))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def add_user(
    user_id: int,
    username: str = None,
    first_name: str = None,
    last_name: str = None,
    phone_number: str = None,
):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users (user_id, username, first_name, last_name, phone_number)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            phone_number = COALESCE(EXCLUDED.phone_number, users.phone_number)
    """,
        (user_id, username, first_name, last_name, phone_number),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def update_user_phone(user_id: int, phone_number: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET phone_number = %s WHERE user_id = %s",
        (phone_number, user_id),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def get_user(user_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return row


def ai_usage_today_count() -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM ai_usage_logs WHERE created_at::date = CURRENT_DATE"
    )
    count = cur.fetchone()[0]
    cur.close()
    release_connection(conn)
    return count


def ai_usage_log(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO ai_usage_logs (user_id) VALUES (%s)", (user_id,))
    conn.commit()
    cur.close()
    release_connection(conn)


def get_all_registered_users():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM users ORDER BY registered_at DESC")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return rows


def get_all_user_ids():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [r["user_id"] for r in rows]


def delete_all_data():
    conn = get_connection()
    cur = conn.cursor()
    # Tashqi kalitlar (Foreign Keys) sababli o'chirish tartibi muhim
    cur.execute("DELETE FROM access_requests")
    cur.execute("DELETE FROM test_natijalari")
    cur.execute("DELETE FROM appeals")
    cur.execute("DELETE FROM mock_natijalari")
    cur.execute("DELETE FROM ota_ona_bog")
    cur.execute("DELETE FROM chatbot_logs")
    cur.execute("DELETE FROM talabalar")
    cur.execute("DELETE FROM test_kalitlari")
    # Ixtiyoriy: Yo'nalishlar va sinflarni ham tozalash mumkin,
    # lekin odatda ular qolishi kerak. Foydalanuvchi "Barcha o'quvchilar va natijalar" degan.
    conn.commit()
    cur.close()
    release_connection(conn)


def statistika():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT COUNT(*) as jami FROM talabalar")
    jami = cur.fetchone()["jami"]
    if jami == 0:
        cur.close()
        release_connection(conn)
        return None
    cur.execute("""
        SELECT AVG(umumiy_ball) as ortacha,
               MAX(umumiy_ball) as eng_yuqori,
               MIN(umumiy_ball) as eng_past
        FROM test_natijalari
    """)
    stat = cur.fetchone()
    cur.close()
    release_connection(conn)
    return {
        "jami": jami,
        "ortacha": round(float(stat["ortacha"]), 2) if stat["ortacha"] else 0,
        "eng_yuqori": stat["eng_yuqori"] if stat["eng_yuqori"] else 0,
        "eng_past": stat["eng_past"] if stat["eng_past"] else 0,
    }


def statistika_by_maktab(maktab_id: int):
    """Maktab bo'yicha statistika"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT COUNT(*) as jami FROM talabalar WHERE maktab_id = %s", (maktab_id,))
    jami = cur.fetchone()["jami"]
    if jami == 0:
        cur.close()
        release_connection(conn)
        return None
    cur.execute("""
        SELECT AVG(n.umumiy_ball) as ortacha,
               MAX(n.umumiy_ball) as eng_yuqori,
               MIN(n.umumiy_ball) as eng_past
        FROM talabalar t
        JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        WHERE t.maktab_id = %s
    """, (maktab_id,))
    stat = cur.fetchone()
    cur.close()
    release_connection(conn)
    return {
        "jami": jami,
        "ortacha": round(float(stat["ortacha"]), 2) if stat["ortacha"] else 0,
        "eng_yuqori": stat["eng_yuqori"] if stat["eng_yuqori"] else 0,
        "eng_past": stat["eng_past"] if stat["eng_past"] else 0,
    }


def talaba_filtrlangan(sinf: str = None, yonalish: str = None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = """
        SELECT t.*, n.umumiy_ball, n.majburiy, n.asosiy_1, n.asosiy_2, n.test_sanasi
        FROM talabalar t
        LEFT JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        WHERE 1=1
    """
    params = []
    if sinf:
        query += " AND t.sinf = %s"
        params.append(sinf)
    if yonalish:
        query += " AND t.yonalish = %s"
        params.append(yonalish)

    query += " ORDER BY t.sinf ASC, n.umumiy_ball DESC NULLS LAST"

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def talaba_filtrlangan_by_maktab(maktab_id: int, sinf: str = None, yonalish: str = None):
    """Maktab bo'yicha filtrlangan talabalarni olish"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = """
        SELECT t.*, n.umumiy_ball, n.majburiy, n.asosiy_1, n.asosiy_2, n.test_sanasi
        FROM talabalar t
        LEFT JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        WHERE t.maktab_id = %s
    """
    params = [maktab_id]
    if sinf:
        query += " AND t.sinf = %s"
        params.append(sinf)
    if yonalish:
        query += " AND t.yonalish = %s"
        params.append(yonalish)

    query += " ORDER BY t.sinf ASC, n.umumiy_ball DESC NULLS LAST"

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_all_in_class(sinf: str):
    """Sinfdagi barcha o'quvchilar natijalarini ballar bo'yicha kamayish tartibida qaytaradi."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT t.kod, t.ismlar, t.yonalish, n.umumiy_ball
        FROM talabalar t
        JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        WHERE t.sinf = %s
        ORDER BY n.umumiy_ball DESC
    """,
        (sinf,),
    )
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_overall_ranking(sinf_prefix: str = None):
    """
    Umumiy Top 50 reytingini qaytaradi.
    Agar sinf_prefix (masalan '9') berilsa, faqat o'sha parallel sinflar (9-A, 9-B va h.k.) bo'yicha qaytaradi.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = """
        SELECT t.kod, t.ismlar, t.sinf, n.umumiy_ball
        FROM talabalar t
        JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
    """
    params = []
    if sinf_prefix:
        query += " WHERE t.sinf LIKE %s"
        params.append(f"{sinf_prefix}%")

    query += " ORDER BY n.umumiy_ball DESC LIMIT 50"

    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_student_rank(kod: str):
    """
    O'quvchining sinfdagi va parallel sinflar (Umumiy) orasidagi o'rnini qaytaradi.
    Parallel sinflar o'quvchining sinf raqami (masalan '9') bo'yicha aniqlanadi.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Avval o'quvchining sinfini aniqlaymiz
    cur.execute("SELECT sinf FROM talabalar WHERE kod = %s", (kod.upper(),))
    talaba = cur.fetchone()
    if not talaba or not talaba["sinf"]:
        cur.close()
        release_connection(conn)
        return {"overall": None, "class": None}

    sinf = talaba["sinf"]
    import re

    match = re.match(r"(\d+)", sinf)
    sinf_prefix = match.group(1) if match else None

    # Sinfdagi o'rni
    cur.execute(
        """
        WITH current_scores AS (
            SELECT t.kod, n.umumiy_ball,
                   RANK() OVER (ORDER BY n.umumiy_ball DESC) as rank
            FROM talabalar t
            JOIN test_natijalari n ON n.id = (
                SELECT id FROM test_natijalari
                WHERE talaba_kod = t.kod
                ORDER BY test_sanasi DESC
                LIMIT 1
            )
            WHERE t.sinf = %s
        )
        SELECT rank FROM current_scores WHERE kod = %s
    """,
        (sinf, kod.upper()),
    )
    class_rank = cur.fetchone()

    # Parallel sinflar orasidagi o'rni (Umumiy)
    overall_rank = None
    if sinf_prefix:
        cur.execute(
            """
            WITH current_scores AS (
                SELECT t.kod, n.umumiy_ball,
                       RANK() OVER (ORDER BY n.umumiy_ball DESC) as rank
                FROM talabalar t
                JOIN test_natijalari n ON n.id = (
                    SELECT id FROM test_natijalari
                    WHERE talaba_kod = t.kod
                    ORDER BY test_sanasi DESC
                    LIMIT 1
                )
                WHERE t.sinf LIKE %s
            )
            SELECT rank FROM current_scores WHERE kod = %s
        """,
            (f"{sinf_prefix}%", kod.upper()),
        )
        overall_rank = cur.fetchone()

    cur.close()
    release_connection(conn)

    res = {"overall": None, "class": None}
    if overall_rank:
        res["overall"] = overall_rank.get("rank")
    if class_rank:
        res["class"] = class_rank.get("rank")

    return res


def get_students_count_by_yonalish(maktab_id: int = None):
    """Yo'nalish bo'yicha o'quvchilar sonini qaytaradi."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if maktab_id:
        cur.execute("""
            SELECT
                COALESCE(yonalish, 'Belgilanmagan') AS yonalish,
                COUNT(*) AS soni
            FROM talabalar
            WHERE maktab_id = %s
            GROUP BY yonalish
            ORDER BY soni DESC
        """, (maktab_id,))
    else:
        cur.execute("""
            SELECT
                COALESCE(yonalish, 'Belgilanmagan') AS yonalish,
                COUNT(*) AS soni
            FROM talabalar
            GROUP BY yonalish
            ORDER BY soni DESC
        """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_avg_score_by_direction():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.yonalish, ROUND(AVG(n.umumiy_ball)::numeric, 2) as avg_score
        FROM talabalar t
        JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        GROUP BY t.yonalish
        ORDER BY avg_score DESC
    """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_avg_score_by_direction_by_maktab(maktab_id: int):
    """Maktab bo'yicha yo'nalishlar bo'yicha o'rtacha ballar"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.yonalish, ROUND(AVG(n.umumiy_ball)::numeric, 2) as avg_score
        FROM talabalar t
        JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        WHERE t.maktab_id = %s
        GROUP BY t.yonalish
        ORDER BY avg_score DESC
    """, (maktab_id,))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_class_comparison():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.sinf, ROUND(AVG(n.umumiy_ball)::numeric, 2) as avg_score
        FROM talabalar t
        JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        GROUP BY t.sinf
        ORDER BY avg_score DESC
    """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_class_comparison_by_maktab(maktab_id: int):
    """Maktab bo'yicha sinflar bo'yicha o'rtacha ballar"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.sinf, ROUND(AVG(n.umumiy_ball)::numeric, 2) as avg_score
        FROM talabalar t
        JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        WHERE t.maktab_id = %s
        GROUP BY t.sinf
        ORDER BY avg_score DESC
    """, (maktab_id,))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_most_improved_students():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        WITH student_diffs AS (
            SELECT talaba_kod,
                   (SELECT umumiy_ball FROM test_natijalari WHERE talaba_kod = t1.talaba_kod ORDER BY test_sanasi DESC LIMIT 1) -
                   (SELECT umumiy_ball FROM test_natijalari WHERE talaba_kod = t1.talaba_kod ORDER BY test_sanasi DESC OFFSET 1 LIMIT 1) as diff
            FROM (SELECT DISTINCT talaba_kod FROM test_natijalari) t1
        )
        SELECT t.kod, t.ismlar, t.sinf, sd.diff
        FROM student_diffs sd
        JOIN talabalar t ON t.kod = sd.talaba_kod
        WHERE sd.diff IS NOT NULL AND sd.diff > 0
        ORDER BY sd.diff DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_most_improved_students_by_maktab(maktab_id: int):
    """Maktab bo'yicha eng ko'p o'sgan o'quvchilar"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        WITH student_diffs AS (
            SELECT talaba_kod,
                   (SELECT umumiy_ball FROM test_natijalari WHERE talaba_kod = t1.talaba_kod ORDER BY test_sanasi DESC LIMIT 1) -
                   (SELECT umumiy_ball FROM test_natijalari WHERE talaba_kod = t1.talaba_kod ORDER BY test_sanasi DESC OFFSET 1 LIMIT 1) as diff
            FROM (SELECT DISTINCT talaba_kod FROM test_natijalari) t1
        )
        SELECT t.kod, t.ismlar, t.sinf, sd.diff
        FROM student_diffs sd
        JOIN talabalar t ON t.kod = sd.talaba_kod
        WHERE sd.diff IS NOT NULL AND sd.diff > 0 AND t.maktab_id = %s
        ORDER BY sd.diff DESC
        LIMIT 10
    """, (maktab_id,))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_most_declined_students():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        WITH student_diffs AS (
            SELECT talaba_kod,
                   (SELECT umumiy_ball FROM test_natijalari WHERE talaba_kod = t1.talaba_kod ORDER BY test_sanasi DESC LIMIT 1) -
                   (SELECT umumiy_ball FROM test_natijalari WHERE talaba_kod = t1.talaba_kod ORDER BY test_sanasi DESC OFFSET 1 LIMIT 1) as diff
            FROM (SELECT DISTINCT talaba_kod FROM test_natijalari) t1
        )
        SELECT t.kod, t.ismlar, t.sinf, sd.diff
        FROM student_diffs sd
        JOIN talabalar t ON t.kod = sd.talaba_kod
        WHERE sd.diff IS NOT NULL AND sd.diff < 0
        ORDER BY sd.diff ASC
        LIMIT 10
    """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def get_most_declined_students_by_maktab(maktab_id: int):
    """Maktab bo'yicha eng ko'p pasaygan o'quvchilar"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        WITH student_diffs AS (
            SELECT talaba_kod,
                   (SELECT umumiy_ball FROM test_natijalari WHERE talaba_kod = t1.talaba_kod ORDER BY test_sanasi DESC LIMIT 1) -
                   (SELECT umumiy_ball FROM test_natijalari WHERE talaba_kod = t1.talaba_kod ORDER BY test_sanasi DESC OFFSET 1 LIMIT 1) as diff
            FROM (SELECT DISTINCT talaba_kod FROM test_natijalari) t1
        )
        SELECT t.kod, t.ismlar, t.sinf, sd.diff
        FROM student_diffs sd
        JOIN talabalar t ON t.kod = sd.talaba_kod
        WHERE sd.diff IS NOT NULL AND sd.diff < 0 AND t.maktab_id = %s
        ORDER BY sd.diff ASC
        LIMIT 10
    """, (maktab_id,))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def appeal_qosh(user_id: int, talaba_kod: str, xabar: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO appeals (user_id, talaba_kod, xabar) VALUES (%s, %s, %s)",
        (user_id, talaba_kod.upper(), xabar),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


# ─────────────────────────────────────────
# Admin sessiyalari tracking
# ─────────────────────────────────────────


def admin_session_start(admin_id: int, admin_name: str):
    """Admin sessiyasini boshlash"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO admin_sessions (admin_id, admin_name, login_time, is_active)
        VALUES (%s, %s, NOW(), true)
    """,
        (admin_id, admin_name),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def admin_session_end(admin_id: int):
    """Admin sessiyasini tugatish"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE admin_sessions 
        SET logout_time = NOW(), is_active = false 
        WHERE admin_id = %s AND is_active = true
    """,
        (admin_id,),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def get_active_admin_sessions():
    """Faol admin sessiyalarini olish"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT admin_id, admin_name, login_time, 
               EXTRACT(EPOCH FROM login_time) as login_epoch,
               CASE WHEN logout_time IS NULL THEN NULL 
                    ELSE EXTRACT(EPOCH FROM logout_time) END as logout_epoch
        FROM admin_sessions 
        WHERE is_active = true 
        ORDER BY login_time DESC
    """)
    sessions = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(s) for s in sessions]


def is_admin_already_active(admin_id: int):
    """Admin allaqachon faol ekanligini tekshirish"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM admin_sessions 
        WHERE admin_id = %s AND is_active = true
    """,
        (admin_id,),
    )
    count = cur.fetchone()[0]
    cur.close()
    release_connection(conn)
    return count > 0


# ─────────────────────────────────────────
# Adminlar boshqarish
# ─────────────────────────────────────────


def create_admins_table():
    """Adminlar jadvalini yaratish"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL UNIQUE,
            username VARCHAR(100),
            full_name VARCHAR(200),
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    release_connection(conn)


def add_admin(user_id: int, username: str = None, full_name: str = None):
    """Yangi admin qo'shish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO admins (user_id, username, full_name) 
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name,
                is_active = true
        """,
            (user_id, username, full_name),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Admin qo'shish xatosi: {e}")
        return False
    finally:
        cur.close()
        release_connection(conn)


def remove_admin(user_id: int):
    """Adminni o'chirish"""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            DELETE FROM admins WHERE user_id = %s
        """,
            (user_id,),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Admin o'chirish xatosi: {e}")
        return False
    finally:
        cur.close()
        release_connection(conn)


def get_all_admins():
    """Barcha adminlarni olish"""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT user_id, username, full_name, is_active, created_at
        FROM admins 
        ORDER BY created_at DESC
    """)
    admins = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(a) for a in admins]


def is_admin_in_db(user_id: int) -> bool:
    """Admin ekanligini database dan tekshirish"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(*) FROM admins WHERE user_id = %s AND is_active = true
    """,
        (user_id,),
    )
    count = cur.fetchone()[0]
    cur.close()
    release_connection(conn)
    return count > 0


def appeals_ol(status: str = "kutilmoqda"):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT a.*, t.ismlar FROM appeals a JOIN talabalar t ON a.talaba_kod = t.kod WHERE a.status = %s ORDER BY a.yaratilgan_sana DESC",
        (status,),
    )
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def appeal_javob_ber(appeal_id: int, javob: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE appeals SET javob = %s, status = 'javob_berildi' WHERE id = %s",
        (javob, appeal_id),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def appeal_ol_id(appeal_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM appeals WHERE id = %s", (appeal_id,))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return dict(row) if row else None


NOTIFICATION_DEFAULTS = {
    "notify_results": True,
    "notify_mock_results": True,
    "notify_admin_messages": True,
    "notify_reminders": True,
}


def get_notification_settings(user_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        INSERT INTO user_notification_settings (user_id)
        VALUES (%s)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id,),
    )
    conn.commit()
    cur.execute(
        "SELECT * FROM user_notification_settings WHERE user_id = %s",
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    data = dict(row) if row else {"user_id": user_id}
    for key, default in NOTIFICATION_DEFAULTS.items():
        data.setdefault(key, default)
    return data


def update_notification_setting(user_id: int, setting_key: str, enabled: bool) -> bool:
    if setting_key not in NOTIFICATION_DEFAULTS:
        return False
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO user_notification_settings (user_id, {0}, updated_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id) DO UPDATE
        SET {0} = EXCLUDED.{0},
            updated_at = CURRENT_TIMESTAMP
        """.format(setting_key),
        (user_id, enabled),
    )
    conn.commit()
    cur.close()
    release_connection(conn)
    return True


def is_notification_enabled(user_id: int, setting_key: str) -> bool:
    settings = get_notification_settings(user_id)
    return bool(settings.get(setting_key, NOTIFICATION_DEFAULTS.get(setting_key, True)))


def get_score_difference(kod: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT umumiy_ball FROM test_natijalari
        WHERE talaba_kod = %s
        ORDER BY test_sanasi DESC
        LIMIT 2
    """,
        (kod.upper(),),
    )
    results = cur.fetchall()
    cur.close()
    release_connection(conn)

    if len(results) < 2:
        return None

    current = float(results[0][0])
    previous = float(results[1][0])
    return round(current - previous, 2)


def get_setting(key: str, default: str = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return row[0] if row else default


def set_setting(key: str, value: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO settings (key, value) 
        VALUES (%s, %s) 
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """,
        (key, value),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def add_access_request(user_id: int, talaba_kod: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO access_requests (user_id, talaba_kod) 
        VALUES (%s, %s)
    """,
        (user_id, talaba_kod.upper()),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def get_pending_requests():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT ar.*, t.ismlar, t.sinf, t.yonalish
        FROM access_requests ar
        JOIN talabalar t ON ar.talaba_kod = t.kod
        WHERE ar.status = 'pending'
        ORDER BY ar.created_at ASC
    """)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def update_request_status(request_id: int, status: str, expires_at=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE access_requests SET status = %s, expires_at = %s WHERE id = %s",
        (status, expires_at, request_id),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def revoke_access_by_user(user_id: int):
    """Foydalanuvchining barcha tasdiqlangan ruxsatlarini 'revoked' holatiga o'tkazadi."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE access_requests SET status = 'revoked' WHERE user_id = %s AND status = 'approved'",
        (user_id,),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def check_access(user_id: int):
    """
    Foydalanuvchining ruxsati borligini tekshiradi.
    Vaqtli ruxsatlarni ham hisobga oladi.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # Status 'approved' bo'lgan va (expires_at NULL yoki hozirgi vaqtdan katta) bo'lgan so'rovni qidiramiz
    cur.execute(
        """
        SELECT 1 FROM access_requests 
        WHERE user_id = %s AND status = 'approved' 
        AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        LIMIT 1
    """,
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return True if row else False


def get_request_by_user(user_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM access_requests WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return dict(row) if row else None


# ─────────────────────────────────────────
# Eslatma tizimi (Reminders)
# ─────────────────────────────────────────


def reminder_qosh(xabar: str, yuborish_vaqti: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reminders (xabar, yuborish_vaqti) VALUES (%s, %s)",
        (xabar, yuborish_vaqti),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def kutilayotgan_reminders_ol():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # Toshkent vaqti (UTC+5) bilan to'g'ri solishtirish
    cur.execute(
        "SELECT * FROM reminders WHERE holat = 'kutilmoqda' AND yuborish_vaqti <= (NOW() AT TIME ZONE 'Asia/Tashkent')"
    )
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def reminder_ochir(reminder_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM reminders WHERE id = %s", (reminder_id,))
    conn.commit()
    cur.close()
    release_connection(conn)


# ─────────────────────────────────────────
# Yangi funktsiyalar uchun ma'lumotlar bazasi funksiyalari
# ─────────────────────────────────────────


# 1. O'quvchi ma'lumotlarini tahrirlash
def talaba_tahrirlash(
    kod: str, ismlar: str = None, sinf: str = None, yonalish: str = None
):
    conn = get_connection()
    cur = conn.cursor()

    update_fields = []
    params = []

    if ismlar is not None:
        update_fields.append("ismlar = %s")
        params.append(ismlar)
    if sinf is not None:
        update_fields.append("sinf = %s")
        params.append(sinf)
    if yonalish is not None:
        update_fields.append("yonalish = %s")
        params.append(yonalish)

    if update_fields:
        params.append(kod)
        query = (
            f"UPDATE talabalar SET {', '.join(update_fields)} WHERE kod = %s"
        )
        cur.execute(query, params)
        conn.commit()

    cur.close()
    release_connection(conn)
    return len(update_fields) > 0


# 2. Maktab bo'yicha statistika
def maktab_statistikasi(maktab_id: int = None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    where_clause = "WHERE t.status = 'aktiv'"
    if maktab_id:
        where_clause += f" AND t.maktab_id = {maktab_id}"

    cur.execute(f"""
        SELECT 
            m.nomi as maktab_nomi,
            t.sinf,
            COUNT(*) as oquvchilar_soni,
            AVG(COALESCE(tn.umumiy_ball, 0)) as ortacha_ball,
            MAX(COALESCE(tn.umumiy_ball, 0)) as eng_yuqori_ball,
            MIN(COALESCE(tn.umumiy_ball, 0)) as eng_past_ball
        FROM talabalar t
        LEFT JOIN test_natijalari tn ON t.kod = tn.talaba_kod
        LEFT JOIN maktablar m ON t.maktab_id = m.id
        {where_clause}
        GROUP BY m.nomi, t.sinf
        ORDER BY m.nomi, t.sinf
    """)

    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


# 3. Faqat bitta natijani o'chirish
def bitta_natija_ochir(talaba_kod: str, natija_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM test_natijalari WHERE id = %s AND talaba_kod = %s",
        (natija_id, talaba_kod),
    )
    affected_rows = cur.rowcount
    conn.commit()
    cur.close()
    release_connection(conn)
    return affected_rows > 0


# 4. Ommaviy sinf transferi
def sinf_transferi(eski_sinf: str, yangi_sinf: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE talabalar SET sinf = %s WHERE sinf = %s",
        (yangi_sinf, eski_sinf),
    )
    affected_rows = cur.rowcount
    conn.commit()
    cur.close()
    release_connection(conn)
    return affected_rows


def sinf_nomi_ol_by_id(sinf_id: int) -> str | None:
    """Sinf ID si bo'yicha sinf nomini qaytaradi."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT nomi FROM sinflar WHERE id = %s", (sinf_id,))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return row["nomi"] if row else None


def sinf_transferi_by_id(eski_sinf_id: int, yangi_sinf_id: int) -> int:
    """Sinf ID lari bo'yicha o'quvchilarni ko'chiradi."""
    eski_nomi = sinf_nomi_ol_by_id(eski_sinf_id)
    yangi_nomi = sinf_nomi_ol_by_id(yangi_sinf_id)
    if not eski_nomi or not yangi_nomi:
        return 0
    return sinf_transferi(eski_nomi, yangi_nomi)


# 5. Bitiruvchilarni arxivlash
def bitiruvchilarni_arxivlash(sinf: str = None):
    conn = get_connection()
    cur = conn.cursor()

    if sinf:
        cur.execute(
            "UPDATE talabalar SET status = 'arxiv' WHERE sinf = %s", (sinf,)
        )
    else:
        # Barcha bitiruvchilarni (11-sinf) arxivlash
        cur.execute(
            "UPDATE talabalar SET status = 'arxiv' WHERE sinf LIKE '11%'"
        )

    affected_rows = cur.rowcount
    conn.commit()
    cur.close()
    release_connection(conn)
    return affected_rows


def bitiruvchilarni_arxivdan_chiqarish(sinf: str = None):
    conn = get_connection()
    cur = conn.cursor()

    if sinf:
        cur.execute(
            "UPDATE talabalar SET status = 'aktiv' WHERE sinf = %s AND status = 'arxiv'",
            (sinf,),
        )
    else:
        cur.execute(
            "UPDATE talabalar SET status = 'aktiv' WHERE status = 'arxiv'"
        )

    affected_rows = cur.rowcount
    conn.commit()
    cur.close()
    release_connection(conn)
    return affected_rows


# 6. Dublikatlarni topish
def dublikatlarni_topish():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT ismlar, COUNT(*) as soni, STRING_AGG(kod, ', ') as kodlar
        FROM talabalar 
        WHERE status = 'aktiv'
        GROUP BY ismlar 
        HAVING COUNT(*) > 1
        ORDER BY soni DESC
    """)

    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


# 7. Dublikatlarni birlashtirish
def dublikatlarni_birlashtir(asosiy_kod: str, qoshimcha_kodlar: list):
    conn = get_connection()
    cur = conn.cursor()

    try:
        # Qo'shimcha talabalarning test natijalarini asosiy talabaga o'tkazish
        for kod in qoshimcha_kodlar:
            cur.execute(
                "UPDATE test_natijalari SET talaba_kod = %s WHERE talaba_kod = %s",
                (asosiy_kod, kod),
            )
            # Qo'shimcha talabani o'chirish
            cur.execute("DELETE FROM talabalar WHERE kod = %s", (kod,))

        conn.commit()
        success = True
    except Exception:
        conn.rollback()
        success = False

    cur.close()
    release_connection(conn)
    return success


# 9. Maktablar ro'yxatini olish
def maktablar_ol():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM maktablar ORDER BY nomi ASC")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def reminder_holat_yangila(reminder_id: int, holat: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE reminders SET holat = %s WHERE id = %s", (holat, reminder_id)
    )
    conn.commit()
    cur.close()
    release_connection(conn)


# ─────────────────────────────────────────
# Ko'p maktab rejimi (Schools)
# ─────────────────────────────────────────


def maktab_qosh(nomi: str):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO maktablar (nomi) VALUES (%s)", (nomi,))
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False


def maktablar_ol():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM maktablar ORDER BY nomi ASC")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


def maktab_ochir(maktab_id: int) -> bool:
    """
    Maktabni o'chiradi. Agar maktabda sinflar bo'lsa, False qaytaradi va o'chirmaydi.
    """
    conn = get_connection()
    cur = conn.cursor()
    # Avval bu maktabga tegishli sinflar borligini tekshiramiz
    cur.execute(
        "SELECT COUNT(*) FROM sinflar WHERE maktab_id = %s", (maktab_id,)
    )
    count = cur.fetchone()[0]
    if count > 0:
        cur.close()
        release_connection(conn)
        return False  # Sinflar bor, o'chirib bo'lmaydi
    cur.execute("DELETE FROM maktablar WHERE id = %s", (maktab_id,))
    conn.commit()
    cur.close()
    release_connection(conn)
    return True


def sinf_maktabga_bogla(full_name: str, maktab_id: int):
    # full_name format: "Sinf nomi - Maktab nomi"
    try:
        parts = full_name.split(" - ")
        sinf_nomi = parts[0]

        conn = get_connection()
        cur = conn.cursor()

        # Yangi maktab nomini olish
        cur.execute("SELECT nomi FROM maktablar WHERE id = %s", (maktab_id,))
        yangi_maktab_nomi = cur.fetchone()[0]
        yangi_full_name = f"{sinf_nomi} - {yangi_maktab_nomi}"

        # Sinflar jadvalini yangilash
        cur.execute(
            "UPDATE sinflar SET maktab_id = %s WHERE nomi = %s AND maktab_id = (SELECT id FROM maktablar WHERE nomi = %s)",
            (maktab_id, sinf_nomi, parts[1]),
        )

        # Talabalar jadvalini yangilash
        cur.execute(
            "UPDATE talabalar SET sinf = %s WHERE sinf = %s",
            (yangi_full_name, full_name),
        )

        conn.commit()
        cur.close()
        release_connection(conn)
    except Exception:
        pass


def maktab_sinflari_ol(maktab_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT nomi FROM sinflar WHERE maktab_id = %s ORDER BY nomi ASC",
        (maktab_id,),
    )
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [r["nomi"] for r in rows]


# ─────────────────────────────────────────
# Guruh rejimi (Groups)
# ─────────────────────────────────────────


def guruh_qosh(chat_id: int, nomi: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO guruhlar (chat_id, nomi) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET nomi = EXCLUDED.nomi",
        (chat_id, nomi),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def guruhlar_ol():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM guruhlar")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]

# Til sozlamalari
def update_user_language(user_id: int, language: str) -> bool:
    """Foydalanuvchi tilini yangilash"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET language = %s WHERE user_id = %s",
            (language, user_id),
        )
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False

def get_user_language(user_id: int) -> str:
    """Foydalanuvchi tilini olish"""
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT language FROM users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        release_connection(conn)
        return result['language'] if result and result['language'] else 'uz'
    except Exception:
        return 'uz'


# ─────────────────────────────────────────
# CHATBOT funksiyalari
# ─────────────────────────────────────────

def create_chatbot_logs_table():
    """Chatbot foydalanish loglarini saqlash jadvali."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chatbot_logs (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            talaba_kod TEXT,
            talaba_ism TEXT,
            savol TEXT NOT NULL,
            javob TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_chatbot_logs_user_id ON chatbot_logs(user_id)"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_chatbot_logs_created_at ON chatbot_logs(created_at)"
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def chatbot_log_qosh(user_id: int, talaba_kod: str, talaba_ism: str, savol: str, javob: str):
    """Chatbot suhbatini loglash."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO chatbot_logs (user_id, talaba_kod, talaba_ism, savol, javob)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (user_id, talaba_kod, talaba_ism, savol[:2000], javob[:4000] if javob else None),
    )
    conn.commit()
    cur.close()
    release_connection(conn)


def chatbot_oxirgi_foydalanuvchilar(limit: int = 20):
    """Chatbotdan so'nggi foydalanuvchilar ro'yxati (admin uchun)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT DISTINCT ON (user_id)
            user_id,
            talaba_ism,
            talaba_kod,
            savol,
            created_at
        FROM chatbot_logs
        ORDER BY user_id, created_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return rows


def chatbot_bugungi_son() -> int:
    """Bugun chatbotdan foydalanganlar soni."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM chatbot_logs WHERE created_at::date = CURRENT_DATE"
    )
    count = cur.fetchone()[0]
    cur.close()
    release_connection(conn)
    return count


def get_user_ids_by_maktab(maktab_id: int):
    """
    Berilgan maktab o'quvchilarining Telegram user_id larini qaytaradi.
    Ikki usul bilan qidiradi:
      1) talabalar.maktab_id orqali (yangi talabalar)
      2) talabalar.sinf => sinflar.maktab_id orqali (eski talabalar)
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT DISTINCT t.user_id
        FROM talabalar t
        WHERE t.user_id IS NOT NULL
          AND (
            t.maktab_id = %(mid)s
            OR t.sinf IN (
                SELECT s.nomi || ' - ' || m.nomi
                FROM sinflar s
                JOIN maktablar m ON s.maktab_id = m.id
                WHERE s.maktab_id = %(mid)s
            )
          )
    """, {"mid": maktab_id})
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [r["user_id"] for r in rows]


def count_users_by_maktab(maktab_id: int) -> int:
    """Berilgan maktabdagi botga ulangan o'quvchilar sonini qaytaradi."""
    return len(get_user_ids_by_maktab(maktab_id))


def talaba_qidirish(query: str, limit: int = 10) -> list:
    """
    Ism bo'yicha o'quvchini qidiradi (katta-kichik harfga sezgir emas).
    Har bir natijaga eng so'nggi test natijasini ham qo'shadi.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """
        SELECT
            t.kod, t.ismlar, t.sinf, t.yonalish,
            tn.umumiy_ball, tn.majburiy, tn.asosiy_1, tn.asosiy_2, tn.test_sanasi
        FROM talabalar t
        LEFT JOIN LATERAL (
            SELECT umumiy_ball, majburiy, asosiy_1, asosiy_2, test_sanasi
            FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        ) tn ON true
        WHERE t.status = 'aktiv'
          AND LOWER(t.ismlar) LIKE LOWER(%s)
        ORDER BY t.ismlar ASC
        LIMIT %s
        """,
        (f"%{query.strip()}%", limit),
    )
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]


# ─────────────────────────────────────────
# Quiz Management
# ─────────────────────────────────────────

def quiz_savollarini_ol(subject: str = None, active_only: bool = False):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sql = "SELECT * FROM practice_questions WHERE 1=1"
    params = []
    if subject:
        sql += " AND subject = %s"
        params.append(subject)
    if active_only:
        sql += " AND is_active = TRUE"
    sql += " ORDER BY subject, id"
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return rows

def quiz_savol_qosh(subject, question, options, correct_option, explanation=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO practice_questions (subject, question, options, correct_option, explanation) VALUES (%s, %s, %s, %s, %s)",
        (subject, question, json.dumps(options), correct_option, explanation)
    )
    conn.commit()
    cur.close()
    release_connection(conn)

def quiz_savol_tahrirla(qid, subject, question, options, correct_option, explanation, is_active):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """UPDATE practice_questions 
           SET subject=%s, question=%s, options=%s, correct_option=%s, explanation=%s, is_active=%s 
           WHERE id=%s""",
        (subject, question, json.dumps(options), correct_option, explanation, is_active, qid)
    )
    conn.commit()
    cur.close()
    release_connection(conn)

def quiz_savol_ochir(qid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM practice_questions WHERE id=%s", (qid,))
    conn.commit()
    cur.close()
    release_connection(conn)

# ─────────────────────────────────────────
# Materials Management
# ─────────────────────────────────────────

def material_ochir(mid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM materiallar WHERE id=%s", (mid,))
    conn.commit()
    cur.close()
    release_connection(conn)

def materiallar_ol_by_subject(active_only=True):
    """Materiallarni fanlar bo'yicha guruhlab beradi."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM materiallar ORDER BY fanni_nomi, yaratilgan_sana DESC")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    
    # Group by subject
    grouped = {}
    for r in rows:
        subject = r["fanni_nomi"] or "Umumiy"
        if subject not in grouped:
            grouped[subject] = []
        grouped[subject].append(r)
    return grouped
def mini_test_qosh(nomi, fan, pdf_file_id, keys, admin_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO mini_testlar (nomi, fan, pdf_file_id, keys, admin_id) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (nomi, fan, pdf_file_id, psycopg2.extras.Json(keys), admin_id)
    )
    test_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    release_connection(conn)
    return test_id

def mini_test_ol(test_id):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM mini_testlar WHERE id = %s", (test_id,))
    res = cur.fetchone()
    cur.close()
    release_connection(conn)
    return res

def mini_test_natija_saqlash(test_id, user_id, talaba_kod, ball, jami_savol):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO mini_test_natijalari (test_id, user_id, talaba_kod, ball, jami_savol) VALUES (%s, %s, %s, %s, %s)",
        (test_id, user_id, talaba_kod, ball, jami_savol)
    )
    conn.commit()
    cur.close()
    release_connection(conn)

def mini_test_hammasi():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM mini_testlar WHERE is_active = TRUE ORDER BY created_at DESC")
    res = cur.fetchall()
    cur.close()
    release_connection(conn)
    return res


# ─── Sinf Taqqoslash (To'liq statistika) ────────────────────────────────────

def get_sinf_detail_stats(sinf: str) -> dict | None:
    """
    Bitta sinf uchun to'liq taqqoslash statistikasini qaytaradi:
    - o'rtacha ball (majburiy, asosiy1, asosiy2, umumiy)
    - eng yuqori / eng past ball
    - o'quvchilar soni
    - Top-3 o'quvchi
    - ball tarqalishi (0-100, 101-130, 131-160, 161-189)
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            COUNT(*)                              AS oquvchilar_soni,
            ROUND(AVG(n.umumiy_ball)::numeric, 1) AS avg_umumiy,
            ROUND(AVG(n.majburiy)::numeric, 1)    AS avg_majburiy,
            ROUND(AVG(n.asosiy_1)::numeric, 1)    AS avg_asosiy1,
            ROUND(AVG(n.asosiy_2)::numeric, 1)    AS avg_asosiy2,
            MAX(n.umumiy_ball)                    AS eng_yuqori,
            MIN(n.umumiy_ball)                    AS eng_past,
            COUNT(CASE WHEN n.umumiy_ball >= 160 THEN 1 END) AS yuqori_soni,
            COUNT(CASE WHEN n.umumiy_ball >= 130
                        AND n.umumiy_ball < 160 THEN 1 END)  AS orta_soni,
            COUNT(CASE WHEN n.umumiy_ball >= 100
                        AND n.umumiy_ball < 130 THEN 1 END)  AS past_soni,
            COUNT(CASE WHEN n.umumiy_ball < 100 THEN 1 END)  AS juda_past_soni
        FROM talabalar t
        JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC LIMIT 1
        )
        WHERE t.sinf = %s AND t.status = 'aktiv'
    """, (sinf,))
    row = cur.fetchone()

    if not row or row["oquvchilar_soni"] == 0:
        cur.close()
        release_connection(conn)
        return None

    # Top-3
    cur.execute("""
        SELECT t.ismlar, n.umumiy_ball
        FROM talabalar t
        JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC LIMIT 1
        )
        WHERE t.sinf = %s AND t.status = 'aktiv'
        ORDER BY n.umumiy_ball DESC LIMIT 3
    """, (sinf,))
    top3 = [dict(r) for r in cur.fetchall()]

    cur.close()
    release_connection(conn)

    result = dict(row)
    result["sinf"] = sinf
    result["top3"] = top3
    return result


def get_two_sinf_comparison(sinf_a: str, sinf_b: str) -> dict | None:
    """
    Ikkita sinfni yonma-yon taqqoslash uchun:
    Har birining to'liq statistikasini va farqlarini qaytaradi.
    """
    a = get_sinf_detail_stats(sinf_a)
    b = get_sinf_detail_stats(sinf_b)
    if not a or not b:
        return None
    return {"a": a, "b": b}
