import psycopg2
import psycopg2.extras
from psycopg2 import pool
import os
from config import MAJBURIY_KOEFF, ASOSIY_1_KOEFF, ASOSIY_2_KOEFF

DATABASE_URL = os.getenv("DATABASE_URL")

# Connection pool — lazy yaratiladi (birinchi so'rovda)
# Bu Railway cold start muammosini hal qiladi
connection_pool = None

def _get_pool():
    global connection_pool
    if connection_pool is None:
        import time
        for attempt in range(5):
            try:
                connection_pool = pool.SimpleConnectionPool(
                    1, 10, DATABASE_URL,
                    sslmode='require',
                    connect_timeout=10
                )
                print("✅ Connection pool muvaffaqiyatli yaratildi")
                break
            except Exception as e:
                print(f"⚠️ Pool yaratish urinish {attempt+1}/5: {e}")
                time.sleep(3)
        if connection_pool is None:
            raise Exception("❌ Supabase ga ulanib bo'lmadi!")
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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS talabalar (
            id SERIAL PRIMARY KEY,
            kod TEXT UNIQUE NOT NULL,
            yonalish TEXT NOT NULL,
            sinf TEXT,
            ismlar TEXT,
            user_id BIGINT DEFAULT NULL,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Index qo'shish (qidiruvni tezlashtirish uchun)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_talabalar_kod ON talabalar(kod)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_talabalar_user_id ON talabalar(user_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS test_natijalari (
            id SERIAL PRIMARY KEY,
            talaba_kod TEXT NOT NULL,
            majburiy INTEGER NOT NULL,
            asosiy_1 INTEGER NOT NULL,
            asosiy_2 INTEGER NOT NULL,
            umumiy_ball REAL NOT NULL,
            test_sanasi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (talaba_kod) REFERENCES talabalar (kod)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_test_natijalari_kod ON test_natijalari(talaba_kod)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            nomi TEXT UNIQUE NOT NULL
        )
    """)

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
    try:
        cur.execute("ALTER TABLE access_requests ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP DEFAULT NULL")
    except Exception:
        pass

    # Default settings
    cur.execute("INSERT INTO settings (key, value) VALUES ('ranking_enabled', 'True') ON CONFLICT DO NOTHING")
    cur.execute("INSERT INTO settings (key, value) VALUES ('stats_enabled', 'True') ON CONFLICT DO NOTHING")

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
        CREATE TABLE IF NOT EXISTS maktablar (
            id SERIAL PRIMARY KEY,
            nomi TEXT UNIQUE NOT NULL,
            yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("INSERT INTO maktablar (nomi) VALUES ('Asosiy maktab') ON CONFLICT DO NOTHING")

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

    # Mavjud jadvallarga maktab_id qo'shish
    tables_to_update = ['talabalar', 'yonalishlar', 'sinflar', 'test_kalitlari']
    for table in tables_to_update:
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS maktab_id INTEGER DEFAULT 1")
        except Exception:
            pass

    cur.execute("SELECT COUNT(*) FROM yonalishlar")
    if cur.fetchone()[0] == 0:
        boshlangich_yonalish = [
            "Matematika + Fizika", "Matematika + Ingliz tili",
            "Matematika + Kimyo", "Matematika + Informatika",
            "Ingliz tili + Ona tili", "Ingliz tili + Tarix",
            "Biologiya + Kimyo", "Tarix + Geografiya"
        ]
        cur.executemany("INSERT INTO yonalishlar (nomi) VALUES (%s) ON CONFLICT DO NOTHING",
                        [(y,) for y in boshlangich_yonalish])

    cur.execute("SELECT COUNT(*) FROM sinflar")
    if cur.fetchone()[0] == 0:
        boshlangich_sinflar = ["11-A", "11-B", "10-A", "10-B", "9-A", "9-B"]
        cur.executemany("INSERT INTO sinflar (nomi) VALUES (%s) ON CONFLICT DO NOTHING",
                        [(s,) for s in boshlangich_sinflar])

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
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT nomi FROM sinflar ORDER BY nomi ASC")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [r["nomi"] for r in rows]

def sinf_qosh(nomi: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO sinflar (nomi) VALUES (%s)", (nomi,))
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False

def sinf_ochir(nomi: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM sinflar WHERE nomi = %s", (nomi,))
    conn.commit()
    cur.close()
    release_connection(conn)


def kalit_qosh(test_nomi: str, kalitlar: str, yonalish: str = None) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO test_kalitlari (test_nomi, yonalish, kalitlar) VALUES (%s, %s, %s)",
            (test_nomi, yonalish, kalitlar.upper())
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
        cur.execute("SELECT * FROM test_kalitlari WHERE test_nomi = %s", (test_nomi,))
        row = cur.fetchone()
        cur.close()
        release_connection(conn)
        return dict(row) if row else None
    elif yonalish:
        cur.execute(
            "SELECT * FROM test_kalitlari WHERE yonalish = %s OR yonalish IS NULL ORDER BY yaratilgan_sana DESC",
            (yonalish,)
        )
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return [dict(r) for r in rows]
    else:
        cur.execute("SELECT * FROM test_kalitlari ORDER BY yaratilgan_sana DESC")
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return [dict(r) for r in rows]

def kalit_tahrirla(test_nomi: str, yangi_kalitlar: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE test_kalitlari SET kalitlar = %s WHERE test_nomi = %s",
                (yangi_kalitlar.upper(), test_nomi))
    conn.commit()
    cur.close()
    release_connection(conn)

def kalit_holat_ozgartir(test_nomi: str, holat: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE test_kalitlari SET holat = %s WHERE test_nomi = %s", (holat, test_nomi))
    conn.commit()
    cur.close()
    release_connection(conn)

def kalit_ochir(test_nomi: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM test_kalitlari WHERE test_nomi = %s", (test_nomi,))
    conn.commit()
    cur.close()
    release_connection(conn)


def ball_hisobla(majburiy: int, asosiy_1: int, asosiy_2: int) -> float:
    ball = (majburiy * MAJBURIY_KOEFF +
            asosiy_1 * ASOSIY_1_KOEFF +
            asosiy_2 * ASOSIY_2_KOEFF)
    return round(ball, 2)


def talaba_qosh(kod: str, yonalish: str, sinf: str = None, ismlar: str = None) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO talabalar (kod, yonalish, sinf, ismlar)
            VALUES (%s, %s, %s, %s)
        """, (kod.upper(), yonalish, sinf, ismlar))
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False

def natija_qosh(talaba_kod: str, majburiy: int, asosiy_1: int, asosiy_2: int) -> bool:
    ball = ball_hisobla(majburiy, asosiy_1, asosiy_2)
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO test_natijalari (talaba_kod, majburiy, asosiy_1, asosiy_2, umumiy_ball)
            VALUES (%s, %s, %s, %s, %s)
        """, (talaba_kod.upper(), majburiy, asosiy_1, asosiy_2, ball))
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False

def talaba_topish(kod: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM talabalar WHERE kod = %s", (kod.upper(),))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return dict(row) if row else None

def talaba_ochir(kod: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        # Avval bog'liq ma'lumotlarni o'chiramiz
        cur.execute("DELETE FROM access_requests WHERE talaba_kod = %s", (kod.upper(),))
        cur.execute("DELETE FROM test_natijalari WHERE talaba_kod = %s", (kod.upper(),))
        cur.execute("DELETE FROM appeals WHERE talaba_kod = %s", (kod.upper(),))
        # Keyin talabaning o'zini
        cur.execute("DELETE FROM talabalar WHERE kod = %s", (kod.upper(),))
        conn.commit()
        cur.close()
        release_connection(conn)
        return True
    except Exception:
        return False

def talaba_natijalari(kod: str, limit: int = 10):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM test_natijalari 
        WHERE talaba_kod = %s 
        ORDER BY test_sanasi DESC 
        LIMIT %s
    """, (kod.upper(), limit))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]

def oqituvchi_qosh(user_id: int, ismlar: str, sinf: str):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO oqituvchilar (user_id, ismlar, sinf) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (user_id) DO UPDATE SET ismlar = EXCLUDED.ismlar, sinf = EXCLUDED.sinf
        """, (user_id, ismlar, sinf))
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
    cur.execute("SELECT * FROM oqituvchilar ORDER BY yaratilgan_sana DESC")
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]

def oqituvchi_ochir(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM oqituvchilar WHERE user_id = %s", (user_id,))
    row_count = cur.rowcount
    conn.commit()
    cur.close()
    release_connection(conn)
    return row_count > 0

def talaba_songi_natija(kod: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM test_natijalari 
        WHERE talaba_kod = %s 
        ORDER BY test_sanasi DESC LIMIT 1
    """, (kod.upper(),))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return dict(row) if row else None

def talaba_natijalari(kod: str, limit: int = None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = "SELECT * FROM test_natijalari WHERE talaba_kod = %s ORDER BY test_sanasi DESC"
    if limit:
        query += f" LIMIT {limit}"
    cur.execute(query, (kod.upper(),))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]

def talaba_songi_natija(kod: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM test_natijalari
        WHERE talaba_kod = %s
        ORDER BY test_sanasi DESC LIMIT 1
    """, (kod.upper(),))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return dict(row) if row else None

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
    cur.execute("UPDATE talabalar SET user_id = %s WHERE kod = %s", (user_id, kod.upper()))
    conn.commit()
    cur.close()
    release_connection(conn)


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


def add_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (user_id, username, first_name, last_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
    """, (user_id, username, first_name, last_name))
    conn.commit()
    cur.close()
    release_connection(conn)

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


def get_all_in_class(sinf: str):
    """Sinfdagi barcha o'quvchilar natijalarini ballar bo'yicha kamayish tartibida qaytaradi."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT t.kod, t.ismlar, n.umumiy_ball
        FROM talabalar t
        JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        WHERE t.sinf = %s
        ORDER BY n.umumiy_ball DESC
    """, (sinf,))
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
    if not talaba or not talaba['sinf']:
        cur.close()
        release_connection(conn)
        return {"overall": None, "class": None}
    
    sinf = talaba['sinf']
    import re
    match = re.match(r'(\d+)', sinf)
    sinf_prefix = match.group(1) if match else None

    # Sinfdagi o'rni
    cur.execute("""
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
    """, (sinf, kod.upper()))
    class_rank = cur.fetchone()
    
    # Parallel sinflar orasidagi o'rni (Umumiy)
    overall_rank = None
    if sinf_prefix:
        cur.execute("""
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
        """, (f"{sinf_prefix}%", kod.upper()))
        overall_rank = cur.fetchone()
    
    cur.close()
    release_connection(conn)
    
    res = {"overall": None, "class": None}
    if overall_rank:
        res["overall"] = overall_rank.get('rank')
    if class_rank:
        res["class"] = class_rank.get('rank')
    
    return res
    


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

def appeal_qosh(user_id: int, talaba_kod: str, xabar: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO appeals (user_id, talaba_kod, xabar) VALUES (%s, %s, %s)", (user_id, talaba_kod.upper(), xabar))
    conn.commit()
    cur.close()
    release_connection(conn)

def appeals_ol(status: str = 'kutilmoqda'):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT a.*, t.ismlar FROM appeals a JOIN talabalar t ON a.talaba_kod = t.kod WHERE a.status = %s ORDER BY a.yaratilgan_sana DESC", (status,))
    rows = cur.fetchall()
    cur.close()
    release_connection(conn)
    return [dict(r) for r in rows]

def appeal_javob_ber(appeal_id: int, javob: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE appeals SET javob = %s, status = 'javob_berildi' WHERE id = %s", (javob, appeal_id))
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

def get_score_difference(kod: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT umumiy_ball FROM test_natijalari
        WHERE talaba_kod = %s
        ORDER BY test_sanasi DESC
        LIMIT 2
    """, (kod.upper(),))
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
    cur.execute("""
        INSERT INTO settings (key, value) 
        VALUES (%s, %s) 
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, (key, value))
    conn.commit()
    cur.close()
    release_connection(conn)

def add_access_request(user_id: int, talaba_kod: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO access_requests (user_id, talaba_kod) 
        VALUES (%s, %s)
    """, (user_id, talaba_kod.upper()))
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
    cur.execute("UPDATE access_requests SET status = %s, expires_at = %s WHERE id = %s", (status, expires_at, request_id))
    conn.commit()
    cur.close()
    release_connection(conn)

def revoke_access_by_user(user_id: int):
    """Foydalanuvchining barcha tasdiqlangan ruxsatlarini 'revoked' holatiga o'tkazadi."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE access_requests SET status = 'revoked' WHERE user_id = %s AND status = 'approved'", (user_id,))
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
    cur.execute("""
        SELECT 1 FROM access_requests 
        WHERE user_id = %s AND status = 'approved' 
        AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        LIMIT 1
    """, (user_id,))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return True if row else False

def get_request_by_user(user_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM access_requests WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,))
    row = cur.fetchone()
    cur.close()
    release_connection(conn)
    return dict(row) if row else None

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

def oqituvchi_qosh(user_id: int, ismlar: str, sinf: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO oqituvchilar (user_id, ismlar, sinf)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET ismlar = EXCLUDED.ismlar, sinf = EXCLUDED.sinf
        """, (user_id, ismlar, sinf))
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

# ─────────────────────────────────────────
# Eslatma tizimi (Reminders)
# ─────────────────────────────────────────

def reminder_qosh(xabar: str, yuborish_vaqti: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO reminders (xabar, yuborish_vaqti) VALUES (%s, %s)", (xabar, yuborish_vaqti))
    conn.commit()
    cur.close()
    release_connection(conn)

def kutilayotgan_reminders_ol():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # UTC vaqt muammosini oldini olish uchun vaqtni biroz kengroq tekshiramiz
    cur.execute("SELECT * FROM reminders WHERE holat = 'kutilmoqda' AND yuborish_vaqti <= (CURRENT_TIMESTAMP + interval '5 hour')")
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

def reminder_holat_yangila(reminder_id: int, holat: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE reminders SET holat = %s WHERE id = %s", (holat, reminder_id))
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

def maktab_ochir(maktab_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM maktablar WHERE id = %s", (maktab_id,))
    conn.commit()
    cur.close()
    release_connection(conn)

def sinf_maktabga_bogla(sinf_nomi: str, maktab_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE sinflar SET maktab_id = %s WHERE nomi = %s", (maktab_id, sinf_nomi))
    conn.commit()
    cur.close()
    release_connection(conn)

def maktab_sinflari_ol(maktab_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT nomi FROM sinflar WHERE maktab_id = %s ORDER BY nomi ASC", (maktab_id,))
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
    cur.execute("INSERT INTO guruhlar (chat_id, nomi) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET nomi = EXCLUDED.nomi", (chat_id, nomi))
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
