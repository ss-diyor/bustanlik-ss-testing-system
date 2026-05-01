import os
import json
import hmac
import hashlib
import logging
import asyncio
from urllib.parse import parse_qsl

from aiohttp import web
import psycopg2
import psycopg2.extras
from config import MAJBURIY_KOEFF, ASOSIY_1_KOEFF, ASOSIY_2_KOEFF

# ─────────────────────────────────────────
# Telegram initData validation
# ─────────────────────────────────────────

def validate_telegram_init_data(init_data: str, bot_token: str) -> tuple[dict | None, str]:
    """
    Telegram WebApp initData ni kriptografik tekshiradi.
    Muvaffaqiyatli bo'lsa (user_dict, "Success") qaytaradi, aks holda (None, xato_sababi).
    """
    if not init_data:
        logging.warning("initData is empty")
        return None, "initData is empty"
        
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            logging.warning("initData missing hash")
            return None, "initData missing hash"

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )
        secret_key = hmac.new(
            b"WebAppData", bot_token.encode(), hashlib.sha256
        ).digest()
        expected_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_hash, received_hash):
            logging.warning("initData hash mismatch")
            return None, "initData hash mismatch"

        return json.loads(parsed.get("user", "{}")), "Success"
    except Exception as e:
        logging.warning(f"initData validation error: {e}")
        return None, f"Exception: {e}"


# ─────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────

STATIC_DIR = os.path.dirname(os.path.abspath(__file__))


async def index_handler(request: web.Request) -> web.Response:
    """Asosiy HTML sahifasini qaytaradi."""
    html_path = os.path.join(STATIC_DIR, "index.html")
    return web.FileResponse(html_path)


async def student_api(request: web.Request) -> web.Response:
    """O'quvchi ma'lumotlarini JSON formatida qaytaradi."""
    from database import get_connection, release_connection

    bot_token = request.app["bot_token"]

    # Telegram initData tekshiruvi
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, err_msg = validate_telegram_init_data(init_data, bot_token)

    if not user:
        # Debug rejimida query param orqali ham ishlaydi
        debug = os.getenv("WEBAPP_DEBUG", "")
        if debug:
            try:
                user_id = int(request.rel_url.query.get("user_id", 0))
            except ValueError:
                return web.json_response({"error": "Invalid user_id"}, status=400)
        else:
            return web.json_response({"error": f"Unauthorized: {err_msg}"}, status=401)
    else:
        user_id = user.get("id", 0)

    if not user_id:
        return web.json_response({"error": "No user_id"}, status=400)

    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # O'quvchi ma'lumotlari
        cur.execute("SELECT * FROM talabalar WHERE user_id = %s", (user_id,))
        talaba = cur.fetchone()

        if not talaba:
            cur.close()
            release_connection(conn)
            return web.json_response({"error": "Student not found"}, status=404)

        # Barcha natijalar (sanasi bo'yicha o'sib boruvchi tartib)
        cur.execute(
            """
            SELECT umumiy_ball, majburiy, asosiy_1, asosiy_2, test_sanasi
            FROM test_natijalari
            WHERE talaba_kod = %s
            ORDER BY test_sanasi ASC
            """,
            (talaba["kod"],),
        )
        natijalar = cur.fetchall()

        # Sinf reytingi
        cur.execute(
            """
            SELECT COUNT(*) + 1 AS sinf_rank
            FROM (
                SELECT DISTINCT ON (tn.talaba_kod) tn.umumiy_ball
                FROM test_natijalari tn
                JOIN talabalar t ON tn.talaba_kod = t.kod
                WHERE t.sinf = %s AND t.status = 'aktiv'
                  AND t.kod != %s
                ORDER BY tn.talaba_kod, tn.test_sanasi DESC
            ) sub
            WHERE sub.umumiy_ball > COALESCE(
                (SELECT umumiy_ball FROM test_natijalari
                 WHERE talaba_kod = %s ORDER BY test_sanasi DESC LIMIT 1), 0
            )
            """,
            (talaba["sinf"], talaba["kod"], talaba["kod"]),
        )
        rank_row = cur.fetchone()
        sinf_rank = rank_row["sinf_rank"] if rank_row else "—"

        # Sinfdoshlar ro'yxati (Faqat ismlar, maxfiylik uchun)
        cur.execute(
            """
            SELECT ismlar
            FROM talabalar
            WHERE sinf = %s AND status = 'aktiv'
            ORDER BY ismlar ASC
            """,
            (talaba["sinf"],)
        )
        classmates = cur.fetchall()

        cur.close()
        release_connection(conn)

        results_list = [
            {
                "umumiy_ball": float(n["umumiy_ball"]),
                "majburiy": float(n["majburiy"]),
                "asosiy_1": float(n["asosiy_1"]),
                "asosiy_2": float(n["asosiy_2"]),
                "sana": n["test_sanasi"].strftime("%d.%m.%Y") if n["test_sanasi"] else "—",
            }
            for n in natijalar
        ]

        # Statistika
        balls = [r["umumiy_ball"] for r in results_list]
        avg = round(sum(balls) / len(balls), 1) if balls else 0
        best = max(balls) if balls else 0
        trend = round(balls[-1] - balls[-2], 1) if len(balls) >= 2 else 0

        return web.json_response(
            {
                "student": {
                    "kod": talaba["kod"],
                    "ismlar": talaba["ismlar"],
                    "sinf": talaba["sinf"],
                    "yonalish": talaba["yonalish"],
                },
                "stats": {
                    "avg": avg,
                    "best": best,
                    "total_tests": len(balls),
                    "trend": trend,
                    "sinf_rank": sinf_rank,
                    "last": balls[-1] if balls else 0,
                },
                "results": results_list,
                "classmates": [
                    {
                        "ismlar": c["ismlar"]
                    }
                    for c in classmates
                ],
                "config": {
                    "MAJBURIY_KOEFF": MAJBURIY_KOEFF,
                    "ASOSIY_1_KOEFF": ASOSIY_1_KOEFF,
                    "ASOSIY_2_KOEFF": ASOSIY_2_KOEFF,
                }
            },
            headers={"Access-Control-Allow-Origin": "*"},
        )

    except Exception as e:
        logging.error(f"Student API error: {e}")
        return web.json_response({"error": "Server error"}, status=500)


async def get_schedule_api(request: web.Request) -> web.Response:
    """O'quvchi uchun testlar taqvimini qaytaradi."""
    from database import get_connection, release_connection
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Kelgusi 30 kunlik testlarni olamiz
        cur.execute("SELECT * FROM test_taqvimi WHERE sana >= CURRENT_DATE ORDER BY sana ASC, vaqt ASC LIMIT 20")
        rows = cur.fetchall()
        for r in rows:
            if r.get("sana"): r["sana"] = r["sana"].strftime("%d.%m.%Y")
        cur.close()
        release_connection(conn)
        return web.json_response({"schedule": rows})
    except Exception as e:
        logging.error(f"Schedule API error: {e}")
        return web.json_response({"error": "Server error"}, status=500)

async def get_materials_api(request: web.Request) -> web.Response:
    """O'quvchi uchun materiallarni qaytaradi."""
    from database import get_connection, release_connection
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM materiallar ORDER BY yaratilgan_sana DESC LIMIT 50")
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return web.json_response({"materials": rows})
    except Exception as e:
        logging.error(f"Materials API error: {e}")
        return web.json_response({"error": "Server error"}, status=500)


async def admin_handler(request: web.Request) -> web.Response:
    """Admin sahifasini qaytaradi."""
    html_path = os.path.join(STATIC_DIR, "admin.html")
    return web.FileResponse(html_path)

async def get_user_role(user_id, conn):
    """Foydalanuvchi rolini aniqlaydi (admin yoki oqituvchi)."""
    from config import ADMIN_IDS
    if user_id in ADMIN_IDS:
        return "admin", None
        
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # admins jadvalini tekshirish
    cur.execute("SELECT user_id FROM admins WHERE user_id = %s", (user_id,))
    if cur.fetchone():
        return "admin", None
        
    # oqituvchilar jadvalini tekshirish
    cur.execute("SELECT sinf FROM oqituvchilar WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    if row:
        return "teacher", row["sinf"]
        
    return None, None

async def admin_stats_api(request: web.Request) -> web.Response:
    """Admin uchun statistik ma'lumotlarni JSON formatida qaytaradi (Role-based)."""
    from config import ADMIN_IDS
    from database import get_connection, release_connection

    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, err_msg = validate_telegram_init_data(init_data, bot_token)

    if not user:
        debug = os.getenv("WEBAPP_DEBUG", "")
        if debug:
            try:
                user_id = int(request.rel_url.query.get("user_id", 0))
            except ValueError:
                return web.json_response({"error": "Invalid user_id"}, status=400)
        else:
            return web.json_response({"error": f"Unauthorized: {err_msg}"}, status=401)
    else:
        user_id = user.get("id", 0)

    try:
        conn = get_connection()
        role, teacher_sinf = await get_user_role(user_id, conn)
        
        if not role:
            release_connection(conn)
            return web.json_response({"error": "Sizda admin yoki o'qituvchi huquqi yo'q!"}, status=403)

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Filter logic
        filter_sql = ""
        params = []
        if role == "teacher" and teacher_sinf:
            filter_sql = " AND sinf = %s"
            params = [teacher_sinf]

        # 1. KPI Stats
        sql_kpi = f"SELECT COUNT(*) as count FROM talabalar WHERE status = 'aktiv' {filter_sql}"
        cur.execute(sql_kpi, params)
        total_students = cur.fetchone()["count"]

        if role == "admin":
            cur.execute("SELECT COUNT(*) as count FROM test_natijalari")
            total_tests = cur.fetchone()["count"]
            cur.execute("SELECT AVG(umumiy_ball) as avg FROM test_natijalari")
            row_avg = cur.fetchone()
            school_avg = row_avg["avg"] or 0
        else:
            # Teacher sees stats for their class only
            cur.execute("SELECT COUNT(*) as count FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod WHERE t.sinf = %s", [teacher_sinf])
            total_tests = cur.fetchone()["count"]
            cur.execute("SELECT AVG(tn.umumiy_ball) as avg FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod WHERE t.sinf = %s", [teacher_sinf])
            row_avg = cur.fetchone()
            school_avg = row_avg["avg"] or 0

        # 2. Class Stats (Admin sees all, Teacher sees only their own)
        if role == "admin":
            cur.execute("SELECT sinf, AVG(umumiy_ball) as avg_score FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod GROUP BY t.sinf ORDER BY t.sinf ASC")
        else:
            cur.execute("SELECT sinf, AVG(umumiy_ball) as avg_score FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod WHERE t.sinf = %s GROUP BY t.sinf", [teacher_sinf])
        class_stats = [{"sinf": r["sinf"], "avg_score": float(r["avg_score"])} for r in cur.fetchall() if r["sinf"]]

        # 3. Direction Stats (Filtered for teacher)
        if role == "admin":
            cur.execute("SELECT yonalish, AVG(umumiy_ball) as avg_score FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod GROUP BY t.yonalish ORDER BY avg_score DESC")
        else:
            cur.execute("SELECT yonalish, AVG(umumiy_ball) as avg_score FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod WHERE t.sinf = %s GROUP BY t.yonalish ORDER BY avg_score DESC", [teacher_sinf])
        direction_stats = [{"yonalish": r["yonalish"], "avg_score": float(r["avg_score"])} for r in cur.fetchall()]

        # 4. Subject Averages
        if role == "admin":
            cur.execute("SELECT AVG(majburiy) as m, AVG(asosiy_1) as a1, AVG(asosiy_2) as a2 FROM test_natijalari")
        else:
            cur.execute("SELECT AVG(majburiy) as m, AVG(asosiy_1) as a1, AVG(asosiy_2) as a2 FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod WHERE t.sinf = %s", [teacher_sinf])
        sub_row = cur.fetchone()
        subject_stats = {
            "majburiy": float(sub_row["m"] or 0),
            "asosiy_1": float(sub_row["a1"] or 0),
            "asosiy_2": float(sub_row["a2"] or 0)
        }
        # 5. Top 30 (Filtered for teacher)
        if role == "admin":
            cur.execute("SELECT t.kod, t.ismlar, t.sinf, t.yonalish, MAX(tn.umumiy_ball) as ball FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod GROUP BY t.kod, t.ismlar, t.sinf, t.yonalish ORDER BY ball DESC LIMIT 30")
        else:
            cur.execute("SELECT t.kod, t.ismlar, t.sinf, t.yonalish, MAX(tn.umumiy_ball) as ball FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod WHERE t.sinf = %s GROUP BY t.kod, t.ismlar, t.sinf, t.yonalish ORDER BY ball DESC LIMIT 30", [teacher_sinf])
        top_students = [{"kod": r["kod"], "ismlar": r["ismlar"], "sinf": r["sinf"], "yonalish": r["yonalish"], "umumiy_ball": float(r["ball"] or 0)} for r in cur.fetchall()]

        cur.close()
        release_connection(conn)

        return web.json_response({
            "role": role,
            "kpi": {"total_students": total_students, "total_tests": total_tests, "school_avg": float(school_avg)},
            "class_stats": class_stats,
            "direction_stats": direction_stats,
            "subject_stats": subject_stats,
            "top_students": top_students
        })
    except Exception as e:
        logging.error(f"Admin API error details: {e}", exc_info=True)
        return web.json_response({"error": f"Server xatosi: {str(e)}"}, status=500)

async def admin_get_schedule_api(request: web.Request) -> web.Response:
    """Testlar taqvimi."""
    from database import get_connection, release_connection
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM test_taqvimi WHERE sana >= CURRENT_DATE ORDER BY sana ASC, vaqt ASC")
        rows = cur.fetchall()
        for r in rows:
            if r.get("sana"): r["sana"] = r["sana"].strftime("%Y-%m-%d")
        cur.close()
        release_connection(conn)
        return web.json_response({"schedule": rows})
    except Exception as e:
        logging.error(f"Schedule GET error: {e}")
        return web.json_response({"error": "Server error"}, status=500)

async def admin_add_schedule_api(request: web.Request) -> web.Response:
    """Yangi test qo'shish (Faqat Admin)."""
    from config import ADMIN_IDS
    from database import get_connection, release_connection
    
    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, _ = validate_telegram_init_data(init_data, bot_token)
    
    if not user or user.get("id", 0) not in ADMIN_IDS:
        return web.json_response({"error": "Unauthorized"}, status=401)
        
    data = await request.json()
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO test_taqvimi (test_nomi, sana, vaqt, sinf) VALUES (%s, %s, %s, %s)",
            (data["test_nomi"], data["sana"], data["vaqt"], data.get("sinf", "Barchaga"))
        )
        conn.commit()
        cur.close()
        release_connection(conn)
        return web.json_response({"success": True})
    except Exception as e:
        logging.error(f"Schedule ADD error: {e}")
        return web.json_response({"error": "Server error"}, status=500)

async def admin_add_material_api(request: web.Request) -> web.Response:
    """Yangi o'quv materiali qo'shish (Faqat Admin)."""
    from config import ADMIN_IDS
    from database import get_connection, release_connection
    
    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, _ = validate_telegram_init_data(init_data, bot_token)
    
    if not user or user.get("id", 0) not in ADMIN_IDS:
        return web.json_response({"error": "Unauthorized"}, status=401)
        
    data = await request.json()
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO materiallar (nomi, turi, link, fanni_nomi, sinf) VALUES (%s, %s, %s, %s, %s)",
            (data["nomi"], data["turi"], data["link"], data.get("fanni_nomi"), data.get("sinf", "Barchaga"))
        )
        conn.commit()
        cur.close()
        release_connection(conn)
        return web.json_response({"success": True})
    except Exception as e:
        logging.error(f"Material ADD error: {e}")
        return web.json_response({"error": "Server error"}, status=500)

async def admin_get_materials_api(request: web.Request) -> web.Response:
    """Barcha materiallarni olish."""
    from database import get_connection, release_connection
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM materiallar ORDER BY yaratilgan_sana DESC")
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return web.json_response({"materials": rows})
    except Exception as e:
        logging.error(f"Admin Materials GET error: {e}")
        return web.json_response({"error": "Server error"}, status=500)

async def admin_delete_material_api(request: web.Request) -> web.Response:
    """Materialni o'chirish."""
    from config import ADMIN_IDS
    from database import material_ochir
    
    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, _ = validate_telegram_init_data(init_data, bot_token)
    
    if not user or user.get("id", 0) not in ADMIN_IDS:
        return web.json_response({"error": "Unauthorized"}, status=401)
        
    mat_id = int(request.match_info['id'])
    try:
        material_ochir(mat_id)
        return web.json_response({"success": True})
    except Exception as e:
        logging.error(f"Material DELETE error: {e}")
        return web.json_response({"error": "Server error"}, status=500)

# Quiz API
async def admin_quiz_api(request: web.Request) -> web.Response:
    """Quiz savollarini boshqarish API."""
    from config import ADMIN_IDS
    from database import quiz_savollarini_ol, quiz_savol_qosh, quiz_savol_tahrirla, quiz_savol_ochir
    
    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, _ = validate_telegram_init_data(init_data, bot_token)
    
    if not user or user.get("id", 0) not in ADMIN_IDS:
        return web.json_response({"error": "Unauthorized"}, status=401)
        
    method = request.method
    
    try:
        if method == "GET":
            questions = quiz_savollarini_ol()
            return web.json_response({"questions": questions})
            
        elif method == "POST":
            data = await request.json()
            quiz_savol_qosh(
                data["subject"], data["question"], data["options"], 
                data["correct_option"], data.get("explanation")
            )
            return web.json_response({"success": True})
            
        elif method == "PUT":
            qid = int(request.match_info['id'])
            data = await request.json()
            
            # Fetch existing to support partial updates
            conn = get_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM practice_questions WHERE id=%s", (qid,))
            existing = cur.fetchone()
            cur.close()
            release_connection(conn)
            
            if not existing:
                return web.json_response({"error": "Not found"}, status=404)
            
            subject = data.get("subject", existing["subject"])
            question = data.get("question", existing["question"])
            options = data.get("options", existing["options"])
            correct_option = data.get("correct_option", existing["correct_option"])
            explanation = data.get("explanation", existing["explanation"])
            is_active = data.get("is_active", existing["is_active"])

            quiz_savol_tahrirla(
                qid, subject, question, options,
                correct_option, explanation, is_active
            )
            return web.json_response({"success": True})
            
        elif method == "DELETE":
            qid = int(request.match_info['id'])
            quiz_savol_ochir(qid)
            return web.json_response({"success": True})
            
    except Exception as e:
        logging.error(f"Quiz Admin API error: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def admin_search_api(request: web.Request) -> web.Response:
    """O'quvchilarni ismi yoki kodi bo'yicha qidirish."""
    from config import ADMIN_IDS
    from database import get_connection, release_connection
    
    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, _ = validate_telegram_init_data(init_data, bot_token)
    
    if not user or user.get("id", 0) not in ADMIN_IDS:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    query = request.rel_url.query.get("q", "").strip()
    if not query:
        return web.json_response({"results": []})
        
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Ism yoki kod bo'yicha qidirish
        sql = "SELECT kod, ismlar, sinf, yonalish FROM talabalar WHERE status = 'aktiv' AND (ismlar ILIKE %s OR kod::text ILIKE %s) LIMIT 20"
        cur.execute(sql, (f"%{query}%", f"%{query}%"))
        results = cur.fetchall()
        
        cur.close()
        release_connection(conn)
        return web.json_response({"results": [dict(r) for r in results]})
    except Exception as e:
        logging.error(f"Search API error: {e}")
        return web.json_response({"error": "Server error"}, status=500)

async def admin_student_details_api(request: web.Request) -> web.Response:
    """Ma'lum bir o'quvchining barcha test tarixini qaytarish."""
    from config import ADMIN_IDS
    from database import get_connection, release_connection
    
    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, _ = validate_telegram_init_data(init_data, bot_token)
    
    if not user or user.get("id", 0) not in ADMIN_IDS:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    student_kod = request.rel_url.query.get("kod", "")
    if not student_kod:
        return web.json_response({"error": "Student code required"}, status=400)
        
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Talaba ma'lumotlari
        cur.execute("SELECT * FROM talabalar WHERE kod = %s", (student_kod,))
        student = cur.fetchone()
        if not student:
            return web.json_response({"error": "Not found"}, status=404)
            
        # Natijalari
        cur.execute("SELECT * FROM test_natijalari WHERE talaba_kod = %s ORDER BY test_sanasi ASC", (student_kod,))
        natijalar = cur.fetchall()
        
        # Format dates
        for n in natijalar:
            if n.get("test_sanasi"):
                n["test_sanasi"] = n["test_sanasi"].strftime("%Y-%m-%d")
        
        cur.close()
        release_connection(conn)
        return web.json_response({
            "student": dict(student),
            "natijalar": [dict(n) for n in natijalar]
        })
    except Exception as e:
        logging.error(f"Details API error: {e}")
        return web.json_response({"error": "Server error"}, status=500)


async def admin_broadcast_api(request: web.Request) -> web.Response:
    """O'quvchilarga xabar yuborish."""
    from config import ADMIN_IDS
    from database import get_connection, release_connection
    from aiogram import Bot
    
    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, _ = validate_telegram_init_data(init_data, bot_token)
    
    if not user or user.get("id", 0) not in ADMIN_IDS:
        return web.json_response({"error": "Unauthorized"}, status=401)
    
    data = await request.json()
    message_text = data.get("text", "").strip()
    target_sinf = data.get("sinf", "Barchaga") # "Barchaga" yoki "9-A"
    
    if not message_text:
        return web.json_response({"error": "Xabar matni bo'sh"}, status=400)
        
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        if target_sinf == "Barchaga":
            cur.execute("SELECT user_id FROM talabalar WHERE status = 'aktiv' AND user_id IS NOT NULL")
        else:
            cur.execute("SELECT user_id FROM talabalar WHERE status = 'aktiv' AND sinf = %s AND user_id IS NOT NULL", (target_sinf,))
            
        users = [r[0] for r in cur.fetchall()]
        cur.close()
        release_connection(conn)
        
        if not users:
            return web.json_response({"error": "O'quvchilar topilmadi"}, status=404)
            
        # Background task as broadcast can take time
        asyncio.create_task(run_broadcast(bot_token, users, message_text))
        
        return web.json_response({"success": True, "count": len(users)})
    except Exception as e:
        logging.error(f"Broadcast API error: {e}")
        return web.json_response({"error": "Server error"}, status=500)

async def run_broadcast(token, user_ids, text):
    from aiogram import Bot
    from aiogram.exceptions import TelegramRetryAfter
    bot = Bot(token=token)
    count = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            count += 1
            if count % 20 == 0: await asyncio.sleep(1) # Simple rate limit handling
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await bot.send_message(uid, text)
        except Exception:
            continue
    await bot.session.close()

async def admin_export_excel_api(request: web.Request) -> web.Response:
    """Statistikani Excel formatida yuklash."""
    from config import ADMIN_IDS
    from database import get_connection, release_connection
    import pandas as pd
    import io
    
    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, _ = validate_telegram_init_data(init_data, bot_token)
    
    if not user or user.get("id", 0) not in ADMIN_IDS:
        return web.json_response({"error": "Unauthorized"}, status=401)
        
    type = request.rel_url.query.get("type", "top_students")
    
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        if type == "top_students":
            query = """
                SELECT t.kod, t.ismlar, t.sinf, t.yonalish, MAX(tn.umumiy_ball) as ball
                FROM test_natijalari tn
                JOIN talabalar t ON tn.talaba_kod = t.kod
                GROUP BY t.kod, t.ismlar, t.sinf, t.yonalish
                ORDER BY ball DESC
            """
            filename = "top_oquvchilar.xlsx"
        elif type == "class_stats":
            query = """
                SELECT t.sinf, AVG(tn.umumiy_ball) as ortacha_ball, COUNT(tn.id) as testlar_soni
                FROM test_natijalari tn
                JOIN talabalar t ON tn.talaba_kod = t.kod
                GROUP BY t.sinf
                ORDER BY t.sinf ASC
            """
            filename = "sinflar_statistikasi.xlsx"
        else:
            return web.json_response({"error": "Invalid type"}, status=400)
            
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        
        if not rows:
            return web.json_response({"error": "Ma'lumotlar topilmadi"}, status=404)
            
        df = pd.DataFrame([dict(r) for r in rows])
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        
        output.seek(0)
        
        return web.Response(
            body=output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logging.error(f"Export API error: {e}", exc_info=True)
        return web.json_response({"error": f"Excel yaratishda xato: {str(e)}"}, status=500)


# ─────────────────────────────────────────
# App factory
# ─────────────────────────────────────────

def create_app(bot_token: str) -> web.Application:
    app = web.Application()
    app["bot_token"] = bot_token

    app.router.add_get("/", index_handler)
    app.router.add_get("/api/student", student_api)
    
    app.router.add_get("/admin", admin_handler)
    app.router.add_get("/api/admin_stats", admin_stats_api)
    app.router.add_get("/api/admin/search", admin_search_api)
    app.router.add_get("/api/admin/student_details", admin_student_details_api)
    app.router.add_post("/api/admin/broadcast", admin_broadcast_api)
    app.router.add_get("/api/admin/export", admin_export_excel_api)
    app.router.add_get("/api/admin/materials", admin_get_materials_api)
    app.router.add_post("/api/admin/materials", admin_add_material_api)
    app.router.add_delete("/api/admin/materials/{id}", admin_delete_material_api)
    
    # Quiz Admin API
    app.router.add_get("/api/admin/quiz", admin_quiz_api)
    app.router.add_post("/api/admin/quiz", admin_quiz_api)
    app.router.add_put("/api/admin/quiz/{id}", admin_quiz_api)
    app.router.add_delete("/api/admin/quiz/{id}", admin_quiz_api)

    # Yangi funksiyalar (Taqvim va Materiallar)
    app.router.add_get("/api/schedule", get_schedule_api)
    app.router.add_get("/api/materials", get_materials_api)

    # CSS / JS / assets
    app.router.add_static("/static", STATIC_DIR)

    return app


async def start_web_server(bot_token: str) -> None:
    """aiohttp web serverni ishga tushiradi (bot bilan parallel)."""
    port = int(os.getenv("PORT", "8080"))
    app = create_app(bot_token)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on 0.0.0.0:{port}")
