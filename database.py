import sqlite3
from datetime import datetime
from config import MAJBURIY_KOEFF, ASOSIY_1_KOEFF, ASOSIY_2_KOEFF

DB_PATH = "dtm_results.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()

    # 1. Talabalar jadvali — user_id ustuni qo'shildi
    conn.execute("""
        CREATE TABLE IF NOT EXISTS talabalar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kod TEXT UNIQUE NOT NULL,
            yonalish TEXT NOT NULL,
            sinf TEXT,
            ismlar TEXT,
            user_id INTEGER DEFAULT NULL,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. Test Natijalari jadvali
    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_natijalari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            talaba_kod TEXT NOT NULL,
            majburiy INTEGER NOT NULL,
            asosiy_1 INTEGER NOT NULL,
            asosiy_2 INTEGER NOT NULL,
            umumiy_ball REAL NOT NULL,
            test_sanasi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (talaba_kod) REFERENCES talabalar (kod)
        )
    """)

    # 3. Foydalanuvchilar jadvali
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 4. Yo'nalishlar jadvali
    conn.execute("""
        CREATE TABLE IF NOT EXISTS yonalishlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomi TEXT UNIQUE NOT NULL
        )
    """)

    # 5. Sinflar jadvali
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sinflar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomi TEXT UNIQUE NOT NULL
        )
    """)

    # 6. Test Kalitlari jadvali — yonalish ustuni qo'shildi
    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_kalitlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_nomi TEXT UNIQUE NOT NULL,
            yonalish TEXT DEFAULT NULL,
            kalitlar TEXT NOT NULL,
            holat TEXT DEFAULT 'ochiq',
            yaratilgan_sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Mavjud jadvalga ustun qo'shish (migration — eski DB uchun)
    try:
        conn.execute("ALTER TABLE talabalar ADD COLUMN user_id INTEGER DEFAULT NULL")
    except Exception:
        pass  # Ustun allaqachon mavjud

    try:
        conn.execute("ALTER TABLE test_kalitlari ADD COLUMN yonalish TEXT DEFAULT NULL")
    except Exception:
        pass  # Ustun allaqachon mavjud

    # Boshlang'ich yo'nalishlar
    count_yonalish = conn.execute("SELECT COUNT(*) FROM yonalishlar").fetchone()[0]
    if count_yonalish == 0:
        boshlangich_yonalish = [
            "Matematika + Fizika", "Matematika + Ingliz tili",
            "Matematika + Kimyo", "Matematika + Informatika",
            "Ingliz tili + Ona tili", "Ingliz tili + Tarix",
            "Biologiya + Kimyo", "Tarix + Geografiya"
        ]
        conn.executemany("INSERT INTO yonalishlar (nomi) VALUES (?)",
                         [(y,) for y in boshlangich_yonalish])

    # Boshlang'ich sinflar
    count_sinflar = conn.execute("SELECT COUNT(*) FROM sinflar").fetchone()[0]
    if count_sinflar == 0:
        boshlangich_sinflar = ["11-A", "11-B", "10-A", "10-B", "9-A", "9-B"]
        conn.executemany("INSERT INTO sinflar (nomi) VALUES (?)",
                         [(s,) for s in boshlangich_sinflar])

    conn.commit()
    conn.close()


# --- Yo'nalish va Sinf funksiyalari ---

def yonalish_ol():
    conn = get_connection()
    rows = conn.execute("SELECT nomi FROM yonalishlar ORDER BY nomi ASC").fetchall()
    conn.close()
    return [r["nomi"] for r in rows]

def yonalish_qosh(nomi: str) -> bool:
    try:
        conn = get_connection()
        conn.execute("INSERT INTO yonalishlar (nomi) VALUES (?)", (nomi,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def yonalish_ochir(nomi: str):
    conn = get_connection()
    conn.execute("DELETE FROM yonalishlar WHERE nomi = ?", (nomi,))
    conn.commit()
    conn.close()

def sinf_ol():
    conn = get_connection()
    rows = conn.execute("SELECT nomi FROM sinflar ORDER BY nomi ASC").fetchall()
    conn.close()
    return [r["nomi"] for r in rows]

def sinf_qosh(nomi: str) -> bool:
    try:
        conn = get_connection()
        conn.execute("INSERT INTO sinflar (nomi) VALUES (?)", (nomi,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def sinf_ochir(nomi: str):
    conn = get_connection()
    conn.execute("DELETE FROM sinflar WHERE nomi = ?", (nomi,))
    conn.commit()
    conn.close()


# --- Test Kalitlari funksiyalari ---

def kalit_qosh(test_nomi: str, kalitlar: str, yonalish: str = None) -> bool:
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO test_kalitlari (test_nomi, yonalish, kalitlar) VALUES (?, ?, ?)",
            (test_nomi, yonalish, kalitlar.upper())
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def kalit_ol(test_nomi: str = None, yonalish: str = None):
    conn = get_connection()
    if test_nomi:
        row = conn.execute("SELECT * FROM test_kalitlari WHERE test_nomi = ?", (test_nomi,)).fetchone()
        conn.close()
        return dict(row) if row else None
    elif yonalish:
        rows = conn.execute(
            "SELECT * FROM test_kalitlari WHERE yonalish = ? OR yonalish IS NULL ORDER BY yaratilgan_sana DESC",
            (yonalish,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    else:
        rows = conn.execute("SELECT * FROM test_kalitlari ORDER BY yaratilgan_sana DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]

def kalit_tahrirla(test_nomi: str, yangi_kalitlar: str):
    conn = get_connection()
    conn.execute("UPDATE test_kalitlari SET kalitlar = ? WHERE test_nomi = ?",
                 (yangi_kalitlar.upper(), test_nomi))
    conn.commit()
    conn.close()

def kalit_holat_ozgartir(test_nomi: str, holat: str):
    conn = get_connection()
    conn.execute("UPDATE test_kalitlari SET holat = ? WHERE test_nomi = ?", (holat, test_nomi))
    conn.commit()
    conn.close()

def kalit_ochir(test_nomi: str):
    conn = get_connection()
    conn.execute("DELETE FROM test_kalitlari WHERE test_nomi = ?", (test_nomi,))
    conn.commit()
    conn.close()


# --- Ball hisoblash ---

def ball_hisobla(majburiy: int, asosiy_1: int, asosiy_2: int) -> float:
    ball = (majburiy * MAJBURIY_KOEFF +
            asosiy_1 * ASOSIY_1_KOEFF +
            asosiy_2 * ASOSIY_2_KOEFF)
    return round(ball, 2)


# --- Talaba va Natija funksiyalari ---

def talaba_qosh(kod: str, yonalish: str, sinf: str = None, ismlar: str = None) -> bool:
    try:
        conn = get_connection()
        conn.execute("""
            INSERT INTO talabalar (kod, yonalish, sinf, ismlar)
            VALUES (?, ?, ?, ?)
        """, (kod.upper(), yonalish, sinf, ismlar))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def natija_qosh(talaba_kod: str, majburiy: int, asosiy_1: int, asosiy_2: int) -> bool:
    ball = ball_hisobla(majburiy, asosiy_1, asosiy_2)
    try:
        conn = get_connection()
        conn.execute("""
            INSERT INTO test_natijalari (talaba_kod, majburiy, asosiy_1, asosiy_2, umumiy_ball)
            VALUES (?, ?, ?, ?, ?)
        """, (talaba_kod.upper(), majburiy, asosiy_1, asosiy_2, ball))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def talaba_topish(kod: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM talabalar WHERE kod=?", (kod.upper(),)).fetchone()
    conn.close()
    return dict(row) if row else None

def talaba_natijalari(kod: str):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM test_natijalari
        WHERE talaba_kod=?
        ORDER BY test_sanasi DESC
    """, (kod.upper(),)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def talaba_songi_natija(kod: str):
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM test_natijalari
        WHERE talaba_kod=?
        ORDER BY test_sanasi DESC LIMIT 1
    """, (kod.upper(),)).fetchone()
    conn.close()
    return dict(row) if row else None

def talaba_user_id_ol(kod: str):
    """Talabaning Telegram user_id sini qaytaradi."""
    conn = get_connection()
    row = conn.execute("SELECT user_id FROM talabalar WHERE kod=?", (kod.upper(),)).fetchone()
    conn.close()
    return row["user_id"] if row else None


# --- Statistika va Ro'yxat ---

def get_all_students_for_excel():
    """
    Har bir talabaning oxirgi natijasini qaytaradi.
    Subquery orqali to'g'ri LEFT JOIN — takrorlanish yo'q.
    """
    conn = get_connection()
    rows = conn.execute("""
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
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def talaba_hammasi():
    """
    Har bir talabaning oxirgi ballini qaytaradi.
    Subquery orqali to'g'ri LEFT JOIN — takrorlanish yo'q.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT t.*,
               n.umumiy_ball
        FROM talabalar t
        LEFT JOIN test_natijalari n ON n.id = (
            SELECT id FROM test_natijalari
            WHERE talaba_kod = t.kod
            ORDER BY test_sanasi DESC
            LIMIT 1
        )
        ORDER BY t.sinf ASC, n.umumiy_ball DESC NULLS LAST
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Foydalanuvchi funksiyalari ---

def add_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
        (user_id, username, first_name, last_name)
    )
    conn.commit()
    conn.close()

def get_all_user_ids():
    conn = get_connection()
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    return [r["user_id"] for r in rows]


# --- Tozalash ---

def delete_all_data():
    conn = get_connection()
    conn.execute("DELETE FROM test_natijalari")
    conn.execute("DELETE FROM talabalar")
    conn.commit()
    conn.close()

def statistika():
    conn = get_connection()
    jami = conn.execute("SELECT COUNT(*) FROM talabalar").fetchone()[0]
    if jami == 0:
        conn.close()
        return None
    stat = conn.execute("""
        SELECT AVG(umumiy_ball) as ortacha,
               MAX(umumiy_ball) as eng_yuqori,
               MIN(umumiy_ball) as eng_past
        FROM test_natijalari
    """).fetchone()
    conn.close()
    return {
        "jami": jami,
        "ortacha": round(stat["ortacha"], 2) if stat["ortacha"] else 0,
        "eng_yuqori": stat["eng_yuqori"] if stat["eng_yuqori"] else 0,
        "eng_past": stat["eng_past"] if stat["eng_past"] else 0,
    }
