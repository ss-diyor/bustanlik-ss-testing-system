import psycopg2
import psycopg2.extras
import os
from config import MAJBURIY_KOEFF, ASOSIY_1_KOEFF, ASOSIY_2_KOEFF

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn


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
        CREATE TABLE IF NOT EXISTS test_kalitlari (
            id SERIAL PRIMARY KEY,
            test_nomi TEXT UNIQUE NOT NULL,
            yonalish TEXT DEFAULT NULL,
            kalitlar TEXT NOT NULL,
            holat TEXT DEFAULT 'ochiq',
            yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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
    conn.close()


def yonalish_ol():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT nomi FROM yonalishlar ORDER BY nomi ASC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r["nomi"] for r in rows]

def yonalish_qosh(nomi: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO yonalishlar (nomi) VALUES (%s)", (nomi,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception:
        return False

def yonalish_ochir(nomi: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM yonalishlar WHERE nomi = %s", (nomi,))
    conn.commit()
    cur.close()
    conn.close()

def sinf_ol():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT nomi FROM sinflar ORDER BY nomi ASC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r["nomi"] for r in rows]

def sinf_qosh(nomi: str) -> bool:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO sinflar (nomi) VALUES (%s)", (nomi,))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception:
        return False

def sinf_ochir(nomi: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM sinflar WHERE nomi = %s", (nomi,))
    conn.commit()
    cur.close()
    conn.close()


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
        conn.close()
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
        conn.close()
        return dict(row) if row else None
    elif yonalish:
        cur.execute(
            "SELECT * FROM test_kalitlari WHERE yonalish = %s OR yonalish IS NULL ORDER BY yaratilgan_sana DESC",
            (yonalish,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    else:
        cur.execute("SELECT * FROM test_kalitlari ORDER BY yaratilgan_sana DESC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]

def kalit_tahrirla(test_nomi: str, yangi_kalitlar: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE test_kalitlari SET kalitlar = %s WHERE test_nomi = %s",
                (yangi_kalitlar.upper(), test_nomi))
    conn.commit()
    cur.close()
    conn.close()

def kalit_holat_ozgartir(test_nomi: str, holat: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE test_kalitlari SET holat = %s WHERE test_nomi = %s", (holat, test_nomi))
    conn.commit()
    cur.close()
    conn.close()

def kalit_ochir(test_nomi: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM test_kalitlari WHERE test_nomi = %s", (test_nomi,))
    conn.commit()
    cur.close()
    conn.close()


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
        conn.close()
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
        conn.close()
        return True
    except Exception:
        return False

def talaba_topish(kod: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM talabalar WHERE kod = %s", (kod.upper(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None

def talaba_natijalari(kod: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT * FROM test_natijalari
        WHERE talaba_kod = %s
        ORDER BY test_sanasi DESC
    """, (kod.upper(),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
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
    conn.close()
    return dict(row) if row else None

def talaba_user_id_ol(kod: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT user_id FROM talabalar WHERE kod = %s", (kod.upper(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row["user_id"] if row else None


def talaba_user_id_yangila(kod: str, user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE talabalar SET user_id = %s WHERE kod = %s", (user_id, kod.upper()))
    conn.commit()
    cur.close()
    conn.close()


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
    conn.close()
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
    conn.close()
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
    conn.close()

def get_all_user_ids():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r["user_id"] for r in rows]


def delete_all_data():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM test_natijalari")
    cur.execute("DELETE FROM talabalar")
    conn.commit()
    cur.close()
    conn.close()

def statistika():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT COUNT(*) as jami FROM talabalar")
    jami = cur.fetchone()["jami"]
    if jami == 0:
        cur.close()
        conn.close()
        return None
    cur.execute("""
        SELECT AVG(umumiy_ball) as ortacha,
               MAX(umumiy_ball) as eng_yuqori,
               MIN(umumiy_ball) as eng_past
        FROM test_natijalari
    """)
    stat = cur.fetchone()
    cur.close()
    conn.close()
    return {
        "jami": jami,
        "ortacha": round(float(stat["ortacha"]), 2) if stat["ortacha"] else 0,
        "eng_yuqori": stat["eng_yuqori"] if stat["eng_yuqori"] else 0,
        "eng_past": stat["eng_past"] if stat["eng_past"] else 0,
    }
