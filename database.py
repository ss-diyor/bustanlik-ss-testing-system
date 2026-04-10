import sqlite3
from config import MAJBURIY_KOEFF, ASOSIY_1_KOEFF, ASOSIY_2_KOEFF

DB_PATH = "dtm_results.db"


def get_connection():
    """Har safar yangi ulanish ochadi. Thread-safe."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # natijani dict kabi ishlatish uchun
    return conn


def init_db():
    """Bazani birinchi marta yaratadi yoki mavjud bo'lsa tekshiradi."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS talabalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kod TEXT UNIQUE NOT NULL,           -- o'quvchining shaxsiy kodi
            yonalish TEXT NOT NULL,             -- tanlagan yo'nalishi
            majburiy INTEGER NOT NULL,          -- majburiy fanlardagi to'g'ri javoblar (0-30)
            asosiy_1 INTEGER NOT NULL,          -- 1-asosiy fandagi to'g'ri javoblar (0-30)
            asosiy_2 INTEGER NOT NULL,          -- 2-asosiy fandagi to'g'ri javoblar (0-30)
            umumiy_ball REAL NOT NULL,          -- hisoblangan umumiy ball
            kiritilgan_vaqt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def ball_hisobla(majburiy: int, asosiy_1: int, asosiy_2: int) -> float:
    """Ball formulasi: majburiy×1.1 + asosiy1×3.1 + asosiy2×2.1"""
    ball = (majburiy * MAJBURIY_KOEFF +
            asosiy_1 * ASOSIY_1_KOEFF +
            asosiy_2 * ASOSIY_2_KOEFF)
    return round(ball, 2)


def talaba_qosh(kod: str, yonalish: str, majburiy: int,
                asosiy_1: int, asosiy_2: int) -> bool:
    """
    Yangi o'quvchi natijasini bazaga qo'shadi.
    Agar bu kod allaqachon mavjud bo'lsa, False qaytaradi.
    """
    ball = ball_hisobla(majburiy, asosiy_1, asosiy_2)
    try:
        conn = get_connection()
        conn.execute("""
            INSERT INTO talabalar (kod, yonalish, majburiy, asosiy_1, asosiy_2, umumiy_ball)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (kod.upper(), yonalish, majburiy, asosiy_1, asosiy_2, ball))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # Unique constraint — bu kod allaqachon bazada bor
        return False


def talaba_yangilash(kod: str, yonalish: str, majburiy: int,
                     asosiy_1: int, asosiy_2: int) -> bool:
    """
    Mavjud o'quvchi natijasini yangilaydi (tahrirlash funksiyasi).
    Agar kod topilmasa, False qaytaradi.
    """
    ball = ball_hisobla(majburiy, asosiy_1, asosiy_2)
    conn = get_connection()
    cur = conn.execute("""
        UPDATE talabalar
        SET yonalish=?, majburiy=?, asosiy_1=?, asosiy_2=?, umumiy_ball=?
        WHERE kod=?
    """, (yonalish, majburiy, asosiy_1, asosiy_2, ball, kod.upper()))
    conn.commit()
    ta_siri = cur.rowcount  # nechta qator o'zgartirildi
    conn.close()
    return ta_siri > 0


def talaba_topish(kod: str):
    """
    Kod bo'yicha o'quvchini topadi.
    Topilsa dict, topilmasa None qaytaradi.
    """
    conn = get_connection()
    cur = conn.execute(
        "SELECT * FROM talabalar WHERE kod=?", (kod.upper(),)
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def statistika():
    """
    Umumiy statistikani qaytaradi:
    - jami kiritilgan o'quvchilar soni
    - o'rtacha ball
    - eng yuqori va eng past ball
    - yo'nalishlar bo'yicha taqsimot
    """
    conn = get_connection()

    umumiy = conn.execute("SELECT COUNT(*) as n FROM talabalar").fetchone()["n"]

    if umumiy == 0:
        conn.close()
        return None

    stat = conn.execute("""
        SELECT
            AVG(umumiy_ball) as ortacha,
            MAX(umumiy_ball) as eng_yuqori,
            MIN(umumiy_ball) as eng_past
        FROM talabalar
    """).fetchone()

    yonalishlar = conn.execute("""
        SELECT yonalish, COUNT(*) as soni
        FROM talabalar
        GROUP BY yonalish
        ORDER BY soni DESC
    """).fetchall()

    conn.close()

    return {
        "jami": umumiy,
        "ortacha": round(stat["ortacha"], 2),
        "eng_yuqori": stat["eng_yuqori"],
        "eng_past": stat["eng_past"],
        "yonalishlar": [dict(r) for r in yonalishlar],
    }
