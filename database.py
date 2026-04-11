import os
import pg8000.native
from config import MAJBURIY_KOEFF, ASOSIY_1_KOEFF, ASOSIY_2_KOEFF
import urllib.parse

# Railway'dan DATABASE_URL ni olamiz
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    """PostgreSQL bazasiga ulanish (pg8000 orqali)."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL o'zgaruvchisi topilmadi!")
    
    url = urllib.parse.urlparse(DATABASE_URL)
    
    conn = pg8000.native.Connection(
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port,
        database=url.path[1:],
        ssl_context=True
    )
    return conn

def init_db():
    """Bazani yaratish va boshlang'ich yo'nalishlarni qo'shish."""
    conn = get_connection()
    # Talabalar jadvali
    conn.run("""
        CREATE TABLE IF NOT EXISTS talabalar (
            id SERIAL PRIMARY KEY,
            kod TEXT UNIQUE NOT NULL,
            yonalish TEXT NOT NULL,
            majburiy INTEGER NOT NULL,
            asosiy_1 INTEGER NOT NULL,
            asosiy_2 INTEGER NOT NULL,
            umumiy_ball REAL NOT NULL,
            kiritilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Yo'nalishlar jadvali
    conn.run("""
        CREATE TABLE IF NOT EXISTS yonalishlar (
            id SERIAL PRIMARY KEY,
            nomi TEXT UNIQUE NOT NULL
        )
    """)

    # Kalitlar (Keys) jadvali
    conn.run("""
        CREATE TABLE IF NOT EXISTS kalitlar (
            id SERIAL PRIMARY KEY,
            yonalish TEXT UNIQUE NOT NULL,
            majburiy_keys TEXT NOT NULL,
            asosiy_1_keys TEXT NOT NULL,
            asosiy_2_keys TEXT NOT NULL
        )
    """)
    
    # Boshlang'ich yo'nalishlar
    res = conn.run("SELECT COUNT(*) FROM yonalishlar")
    if res[0][0] == 0:
        boshlangich = [
            "Matematika + Fizika", "Matematika + Ingliz tili",
            "Matematika + Kimyo", "Matematika + Informatika",
            "Ingliz tili + Ona tili", "Ingliz tili + Tarix",
            "Biologiya + Kimyo", "Tarix + Geografiya"
        ]
        for y in boshlangich:
            conn.run("INSERT INTO yonalishlar (nomi) VALUES (:nomi)", nomi=y)
    conn.close()

# --- Yo'nalishlar ---
def yonalish_ol():
    conn = get_connection()
    rows = conn.run("SELECT nomi FROM yonalishlar ORDER BY nomi ASC")
    conn.close()
    return [row[0] for row in rows]

def yonalish_qosh(nomi: str) -> bool:
    try:
        conn = get_connection()
        conn.run("INSERT INTO yonalishlar (nomi) VALUES (:nomi)", nomi=nomi)
        conn.close()
        return True
    except:
        return False

def yonalish_ochir(nomi: str):
    conn = get_connection()
    conn.run("DELETE FROM yonalishlar WHERE nomi = :nomi", nomi=nomi)
    conn.close()

# --- Kalitlar (Keys) ---
def kalit_qosh(yonalish, majburiy, asosiy1, asosiy2):
    conn = get_connection()
    try:
        conn.run("""
            INSERT INTO kalitlar (yonalish, majburiy_keys, asosiy_1_keys, asosiy_2_keys)
            VALUES (:yonalish, :majburiy, :asosiy1, :asosiy2)
            ON CONFLICT (yonalish) DO UPDATE SET
            majburiy_keys = EXCLUDED.majburiy_keys,
            asosiy_1_keys = EXCLUDED.asosiy_1_keys,
            asosiy_2_keys = EXCLUDED.asosiy_2_keys
        """, yonalish=yonalish, majburiy=majburiy.lower(), asosiy1=asosiy1.lower(), asosiy2=asosiy2.lower())
        return True
    except:
        return False
    finally:
        conn.close()

def kalit_ol(yonalish):
    conn = get_connection()
    res = conn.run("SELECT majburiy_keys, asosiy_1_keys, asosiy_2_keys FROM kalitlar WHERE yonalish = :yonalish", yonalish=yonalish)
    conn.close()
    if res:
        return {"majburiy": res[0][0], "asosiy_1": res[0][1], "asosiy_2": res[0][2]}
    return None

# --- Talabalar ---
def ball_hisobla(majburiy: int, asosiy_1: int, asosiy_2: int) -> float:
    ball = (majburiy * MAJBURIY_KOEFF + asosiy_1 * ASOSIY_1_KOEFF + asosiy_2 * ASOSIY_2_KOEFF)
    return round(ball, 2)

def talaba_qosh(kod: str, yonalish: str, majburiy: int, asosiy_1: int, asosiy_2: int) -> bool:
    ball = ball_hisobla(majburiy, asosiy_1, asosiy_2)
    try:
        conn = get_connection()
        conn.run("""
            INSERT INTO talabalar (kod, yonalish, majburiy, asosiy_1, asosiy_2, umumiy_ball)
            VALUES (:kod, :yonalish, :majburiy, :asosiy_1, :asosiy_2, :ball)
        """, kod=kod.upper(), yonalish=yonalish, majburiy=majburiy, asosiy_1=asosiy_1, asosiy_2=asosiy_2, ball=ball)
        conn.close()
        return True
    except:
        return False

def talaba_yangilash(kod: str, yonalish: str, majburiy: int, asosiy_1: int, asosiy_2: int) -> bool:
    ball = ball_hisobla(majburiy, asosiy_1, asosiy_2)
    conn = get_connection()
    conn.run("""
        UPDATE talabalar
        SET yonalish=:yonalish, majburiy=:majburiy, asosiy_1=:asosiy_1, asosiy_2=:asosiy_2, umumiy_ball=:ball
        WHERE kod=:kod
    """, yonalish=yonalish, majburiy=majburiy, asosiy_1=asosiy_1, asosiy_2=asosiy_2, ball=ball, kod=kod.upper())
    conn.close()
    return True

def talaba_topish(kod: str):
    conn = get_connection()
    res = conn.run("SELECT id, kod, yonalish, majburiy, asosiy_1, asosiy_2, umumiy_ball FROM talabalar WHERE kod=:kod", kod=kod.upper())
    conn.close()
    if res:
        r = res[0]
        return {"id": r[0], "kod": r[1], "yonalish": r[2], "majburiy": r[3], "asosiy_1": r[4], "asosiy_2": r[5], "umumiy_ball": r[6]}
    return None

def talaba_hammasi():
    conn = get_connection()
    res = conn.run("SELECT id, kod, yonalish, majburiy, asosiy_1, asosiy_2, umumiy_ball FROM talabalar ORDER BY umumiy_ball DESC")
    conn.close()
    return [{"id": r[0], "kod": r[1], "yonalish": r[2], "majburiy": r[3], "asosiy_1": r[4], "asosiy_2": r[5], "umumiy_ball": r[6]} for r in res]

def statistika():
    conn = get_connection()
    res = conn.run("SELECT COUNT(*) FROM talabalar")
    conn.close()
    umumiy = res[0][0]
    return {"jami": umumiy} if umumiy > 0 else None
