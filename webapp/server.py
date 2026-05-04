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
from datetime import datetime
from config import MAJBURIY_KOEFF, ASOSIY_1_KOEFF, ASOSIY_2_KOEFF

def json_serializer(obj):
    """JSON uchun datetime va boshqa obyektlarni serializatsiya qiladi."""
    if isinstance(obj, (datetime)):
        return obj.isoformat()
    return str(obj)

def safe_json_response(data, status=200):
    """Datetime obyektlarini qo'llab-quvvatlaydigan json_response."""
    return web.json_response(
        data, 
        status=status, 
        dumps=lambda x: json.dumps(x, default=json_serializer)
    )

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


async def health_handler(request: web.Request) -> web.Response:
    """Railway/Render health check uchun."""
    return web.json_response({"status": "ok"})


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
        return safe_json_response({"schedule": rows})
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
        return safe_json_response({"materials": rows})
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
    
async def check_admin_role(request: web.Request):
    """Helper: Auth tekshirish va rolni qaytarish."""
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
                return None, None, web.json_response({"error": "Invalid user_id"}, status=400)
        else:
            return None, None, web.json_response({"error": f"Unauthorized: {err_msg}"}, status=401)
    else:
        user_id = user.get("id", 0)

    conn = get_connection()
    role, teacher_sinf = await get_user_role(user_id, conn)
    release_connection(conn)
    
    if not role:
        return None, None, web.json_response({"error": "Sizda admin yoki o'qituvchi huquqi yo'q!"}, status=403)
        
    return role, teacher_sinf, None

async def admin_stats_api(request: web.Request) -> web.Response:
    """Admin uchun statistik ma'lumotlarni JSON formatida qaytaradi (Role-based)."""
    role, teacher_sinf, error_resp = await check_admin_role(request)
    if error_resp: return error_resp
    
    # user_id ni check_admin_role dan olish uchun kichik trick yoki qayta hisoblash
    # validate_telegram_init_data natijasini keshlasak bo'ladi, lekin hozircha user_id ni qayta olamiz
    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, _ = validate_telegram_init_data(init_data, bot_token)
    user_id = user.get("id", 0) if user else int(request.rel_url.query.get("user_id", 0))

    try:
        from database import get_connection, release_connection
        conn = get_connection()

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
    role, _, error_resp = await check_admin_role(request)
    if error_resp: return error_resp
    
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
    role, _, error_resp = await check_admin_role(request)
    if error_resp: return error_resp
    if role != "admin":
        return web.json_response({"error": "Faqat adminlar test qo'sha oladi"}, status=403)
        
    from database import get_connection, release_connection
        
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
    role, _, error_resp = await check_admin_role(request)
    if error_resp: return error_resp
    if role != "admin":
        return web.json_response({"error": "Faqat adminlar material qo'sha oladi"}, status=403)
        
    from database import get_connection, release_connection
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
    role, _, error_resp = await check_admin_role(request)
    if error_resp: return error_resp
    
    from database import get_connection, release_connection
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM materiallar ORDER BY yaratilgan_sana DESC")
        rows = cur.fetchall()
        cur.close()
        release_connection(conn)
        return safe_json_response({"materials": rows})
    except Exception as e:
        logging.error(f"Admin Materials GET error: {e}")
        return web.json_response({"error": "Server error"}, status=500)

async def admin_delete_material_api(request: web.Request) -> web.Response:
    """Materialni o'chirish."""
    role, _, error_resp = await check_admin_role(request)
    if error_resp: return error_resp
    if role != "admin":
        return web.json_response({"error": "Faqat adminlar material o'chira oladi"}, status=403)
        
    from database import material_ochir
        
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
    role, _, error_resp = await check_admin_role(request)
    if error_resp: return error_resp
    if role != "admin":
        return web.json_response({"error": "Faqat adminlar quiz boshqara oladi"}, status=403)
        
    from database import quiz_savollarini_ol, quiz_savol_qosh, quiz_savol_tahrirla, quiz_savol_ochir
    from database import get_connection, release_connection
        
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
    role, _, error_resp = await check_admin_role(request)
    if error_resp: return error_resp
    
    from database import get_connection, release_connection
    
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
    role, _, error_resp = await check_admin_role(request)
    if error_resp: return error_resp
    
    from database import get_connection, release_connection
    
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
    role, _, error_resp = await check_admin_role(request)
    if error_resp: return error_resp
    if role != "admin":
        return web.json_response({"error": "Faqat adminlar xabar yubora oladi"}, status=403)
        
    from database import get_connection, release_connection
    
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
    role, _, error_resp = await check_admin_role(request)
    if error_resp: return error_resp
    
    from database import get_connection, release_connection
    import pandas as pd
    import io
        
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



async def verify_handler(request: web.Request) -> web.Response:
    """Sertifikatni QR-kod orqali tekshirish sahifasi — hamma uchun ochiq."""
    from database import get_connection, release_connection
    kod = request.match_info.get("kod", "").strip().upper()
    if not kod:
        raise web.HTTPNotFound()

    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("SELECT * FROM talabalar WHERE kod = %s", (kod,))
        talaba = cur.fetchone()
        if not talaba:
            cur.close(); release_connection(conn)
            return web.Response(
                content_type="text/html",
                text=_verify_not_found_html(kod),
            )

        cur.execute(
            """SELECT umumiy_ball, majburiy, asosiy_1, asosiy_2, test_sanasi
               FROM test_natijalari WHERE talaba_kod = %s
               ORDER BY test_sanasi DESC LIMIT 1""",
            (kod,),
        )
        natija = cur.fetchone()
        cur.close(); release_connection(conn)
    except Exception as e:
        logging.error(f"verify_handler error: {e}")
        raise web.HTTPInternalServerError()

    # Hash tekshiruvi (blockchain verification)
    hash_valid = False
    stored_hash = talaba.get("cert_hash") or ""
    if stored_hash and natija:
        try:
            from certificate import generate_cert_hash
            sana = str(natija.get("test_sanasi", ""))[:10]
            expected = generate_cert_hash(
                kod, talaba.get("ismlar", ""), natija.get("umumiy_ball", 0), sana
            )
            hash_valid = (expected == stored_hash)
        except Exception:
            hash_valid = False
    elif not stored_hash:
        # Eski sertifikatlar (hash yo'q) — ishonchli deb qabul qilish
        hash_valid = True

    return web.Response(
        content_type="text/html",
        text=_verify_success_html(talaba, natija, stored_hash, hash_valid),
    )


def _get_verify_config() -> tuple[str, str]:
    """Bot username va logo URL ni config'dan oladi."""
    try:
        from config import BOT_USERNAME, VERIFY_BASE_URL
        bot_user = BOT_USERNAME or "bustanlik_ss_bot"
        logo_url = f"{VERIFY_BASE_URL}/static/logo.png"
    except Exception:
        bot_user = "bustanlik_ss_bot"
        logo_url = ""
    return bot_user, logo_url


_VERIFY_CSS = """
  :root {
    --primary: #1a5276;
    --primary-light: #2980b9;
    --accent: #16a085;
    --accent-light: #1abc9c;
    --gold: #d4ac0d;
    --bg: #0f2744;
    --card-bg: #ffffff;
    --text: #1a202c;
    --muted: #5a6a7a;
    --border: #e2e8f0;
    --success: #1e8449;
    --danger: #c0392b;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: linear-gradient(160deg, #0f2744 0%, #1a4a7a 50%, #0d3b5e 100%);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px 16px;
  }
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background: radial-gradient(ellipse at 20% 30%, rgba(41,128,185,.15) 0%, transparent 60%),
                radial-gradient(ellipse at 80% 70%, rgba(22,160,133,.12) 0%, transparent 60%);
    pointer-events: none;
  }
  .wrapper { width: 100%; max-width: 460px; position: relative; }
  .card {
    background: #fff;
    border-radius: 24px;
    overflow: hidden;
    box-shadow: 0 24px 80px rgba(0,0,0,.35), 0 4px 16px rgba(0,0,0,.15);
    position: relative;
  }
  /* Header band */
  .header-band {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
    padding: 28px 24px 20px;
    text-align: center;
    position: relative;
    overflow: hidden;
  }
  .header-band::after {
    content: '';
    position: absolute;
    bottom: -1px; left: 0; right: 0;
    height: 20px;
    background: #fff;
    border-radius: 50% 50% 0 0 / 100% 100% 0 0;
  }
  .school-logo {
    width: 72px; height: 72px;
    border-radius: 50%;
    border: 3px solid rgba(255,255,255,.4);
    object-fit: cover;
    margin-bottom: 10px;
    background: rgba(255,255,255,.15);
  }
  .logo-placeholder {
    width: 72px; height: 72px;
    border-radius: 50%;
    border: 3px solid rgba(255,255,255,.4);
    background: rgba(255,255,255,.15);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 2em;
    margin-bottom: 10px;
  }
  .school-name {
    color: rgba(255,255,255,.9);
    font-size: .78em;
    font-weight: 600;
    letter-spacing: .06em;
    text-transform: uppercase;
  }
  /* Body */
  .body { padding: 8px 28px 28px; text-align: center; }
  /* Status badge */
  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 16px;
    border-radius: 100px;
    font-size: .8em;
    font-weight: 700;
    letter-spacing: .04em;
    margin-bottom: 16px;
  }
  .status-badge.valid {
    background: #d5f5e3;
    color: var(--success);
    border: 1px solid #a9dfbf;
  }
  .status-badge.no-hash {
    background: #fef9e7;
    color: #b7950b;
    border: 1px solid #f9e79f;
  }
  /* Name */
  .student-name {
    font-size: 1.55em;
    font-weight: 800;
    color: var(--text);
    margin-bottom: 4px;
    line-height: 1.2;
  }
  .student-meta {
    color: var(--muted);
    font-size: .85em;
    margin-bottom: 22px;
  }
  .sep { margin: 0 6px; opacity: .4; }
  /* Score */
  .score-block {
    background: linear-gradient(135deg, #eaf4fb 0%, #e8f8f5 100%);
    border-radius: 16px;
    padding: 20px 16px 16px;
    margin-bottom: 16px;
    border: 1px solid #d6eaf8;
  }
  .score-num {
    font-size: 3.5em;
    font-weight: 900;
    background: linear-gradient(135deg, var(--primary), var(--accent));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1;
  }
  .score-max { font-size: .38em; color: #a0aec0; font-weight: 400; }
  .score-pct {
    color: var(--accent);
    font-weight: 700;
    font-size: 1em;
    margin: 4px 0 14px;
  }
  /* Breakdown */
  .breakdown { text-align: left; }
  .brow {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 0;
    border-bottom: 1px solid rgba(0,0,0,.06);
    font-size: .88em;
    color: #4a5568;
  }
  .brow:last-child { border-bottom: none; }
  .brow b { color: var(--text); }
  /* Hash block */
  .hash-block {
    background: #f8f9fa;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 16px;
    text-align: left;
  }
  .hash-label {
    font-size: .72em;
    font-weight: 700;
    color: var(--muted);
    letter-spacing: .07em;
    text-transform: uppercase;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .hash-value {
    font-family: 'Courier New', monospace;
    font-size: .68em;
    color: #4a5568;
    word-break: break-all;
    line-height: 1.5;
  }
  /* Kod */
  .cert-kod {
    display: inline-block;
    background: #edf2f7;
    color: #4a5568;
    padding: 7px 18px;
    border-radius: 100px;
    font-family: monospace;
    font-size: .9em;
    margin-bottom: 20px;
    border: 1px solid var(--border);
  }
  /* Footer */
  .card-footer {
    border-top: 1px solid var(--border);
    padding: 18px 24px 22px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    background: #fafbfc;
    text-align: center;
  }
  .footer-hint {
    font-size: .75em;
    color: var(--muted);
  }
  .tg-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #0088cc;
    color: #fff;
    text-decoration: none;
    padding: 9px 20px;
    border-radius: 100px;
    font-size: .82em;
    font-weight: 600;
    white-space: nowrap;
  }
  .tg-link svg { width: 15px; height: 15px; fill: #fff; }
  .no-result { color: #a0aec0; font-style: italic; padding: 16px 0; }
"""

_VERIFY_NOT_FOUND_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: linear-gradient(160deg, #0f2744 0%, #1a4a7a 50%, #0d3b5e 100%);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  }
  .card {
    background: #fff;
    border-radius: 24px;
    padding: 48px 36px;
    text-align: center;
    box-shadow: 0 24px 80px rgba(0,0,0,.35);
    max-width: 400px;
    width: 100%;
  }
  .icon { font-size: 64px; margin-bottom: 20px; }
  h2 { color: #c0392b; font-size: 1.4em; margin-bottom: 8px; }
  p { color: #718096; font-size: .9em; margin-bottom: 6px; }
  .kod {
    display: inline-block;
    background: #fff5f5;
    color: #c0392b;
    padding: 8px 20px;
    border-radius: 100px;
    font-family: monospace;
    font-size: 1.1em;
    margin-top: 16px;
    border: 1px solid #fed7d7;
  }
  .tg-hint {
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid #e2e8f0;
  }
  .tg-link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #0088cc;
    color: #fff;
    text-decoration: none;
    padding: 9px 18px;
    border-radius: 100px;
    font-size: .85em;
    font-weight: 600;
    margin-top: 10px;
  }
"""


def _verify_not_found_html(kod: str) -> str:
    bot_user, _ = _get_verify_config()
    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Sertifikat topilmadi</title>
  <style>{_VERIFY_NOT_FOUND_CSS}</style>
</head>
<body>
  <div class="card">
    <div class="icon">🔍</div>
    <h2>Sertifikat topilmadi</h2>
    <p>Bunday kodli o'quvchi tizimda mavjud emas.</p>
    <p>Kod to'g'ri ekanligini tekshiring.</p>
    <div class="kod">{kod}</div>
    <div class="tg-hint">
      <p style="color:#a0aec0;font-size:.82em">Savollar uchun Telegram bot:</p>
      <a class="tg-link" href="https://t.me/{bot_user}" target="_blank">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="width:16px;height:16px;fill:#fff">
          <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/>
        </svg>
        @{bot_user}
      </a>
    </div>
  </div>
</body>
</html>"""


def _verify_success_html(talaba: dict, natija: dict | None,
                         cert_hash: str = "", hash_valid: bool = True) -> str:
    bot_user, logo_url = _get_verify_config()
    ism  = talaba.get("ismlar", "")
    sinf = talaba.get("sinf", "—")
    yo   = talaba.get("yonalish", "—")
    kod  = talaba.get("kod", "")

    # Logo HTML
    if logo_url:
        logo_html = f'<img src="{logo_url}" class="school-logo" alt="Maktab logosi" onerror="this.style.display=\'none\'">'
    else:
        logo_html = '<div class="logo-placeholder">🏫</div>'

    # Hash status badge
    if cert_hash:
        badge_html = '<span class="status-badge valid">✅ &nbsp;Sertifikat haqiqiy — tasdiqlandi</span>'
    else:
        badge_html = '<span class="status-badge no-hash">⚠️ &nbsp;Sertifikat tasdiqlandi (eski format)</span>'

    # Hash block
    if cert_hash:
        short_hash = cert_hash[:16] + "…" + cert_hash[-8:]
        hash_block = f"""
        <div class="hash-block">
          <div class="hash-label">🔐 Blockchain hash (SHA-256)</div>
          <div class="hash-value">{cert_hash}</div>
        </div>"""
    else:
        hash_block = ""

    # Natija bloki
    if natija:
        ball = natija.get("umumiy_ball", 0)
        sana = str(natija.get("test_sanasi", ""))[:10]
        foiz = round(float(ball) / 189 * 100, 1)
        maj  = natija.get("majburiy", 0)
        as1  = natija.get("asosiy_1", 0)
        as2  = natija.get("asosiy_2", 0)
        natija_blok = f"""
        <div class="score-block">
          <div class="score-num">{ball}<span class="score-max"> / 189</span></div>
          <div class="score-pct">{foiz}%</div>
          <div class="breakdown">
            <div class="brow"><span>📘 Majburiy fanlar</span><b>{maj}/30</b></div>
            <div class="brow"><span>📗 1-asosiy fan</span><b>{as1}/30</b></div>
            <div class="brow"><span>📙 2-asosiy fan</span><b>{as2}/30</b></div>
            <div class="brow"><span>📅 Test sanasi</span><b>{sana}</b></div>
          </div>
        </div>"""
    else:
        natija_blok = '<div class="no-result">Hali test natijalari mavjud emas</div>'

    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Sertifikat — {ism}</title>
  <style>{_VERIFY_CSS}</style>
</head>
<body>
<div class="wrapper">
  <div class="card">
    <div class="header-band">
      {logo_html}
      <div class="school-name">Bo'stonliq tuman ixtisoslashtirilgan maktabi</div>
    </div>

    <div class="body">
      {badge_html}
      <div class="student-name">{ism}</div>
      <div class="student-meta">{sinf}<span class="sep">|</span>{yo}</div>

      {natija_blok}

      {hash_block}

      <div class="cert-kod">🆔 Kod: {kod}</div>
    </div>

    <div class="card-footer">
      <div class="footer-hint">Bu sahifa sertifikat haqiqiyligini tasdiqlaydi</div>
      <a class="tg-link" href="https://t.me/{bot_user}" target="_blank">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12l-6.871 4.326-2.962-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.833.941z"/>
        </svg>
        @{bot_user}
      </a>
    </div>
  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────
# App factory
# ─────────────────────────────────────────

def create_app(bot_token: str) -> web.Application:
    app = web.Application()
    app["bot_token"] = bot_token

    app.router.add_get("/", index_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/verify/{kod}", verify_handler)
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

    # Admin Schedule API
    app.router.add_get("/api/admin/schedule", admin_get_schedule_api)
    app.router.add_post("/api/admin/schedule", admin_add_schedule_api)

    # Yangi funksiyalar (Taqvim va Materiallar)
    app.router.add_get("/api/schedule", get_schedule_api)
    app.router.add_get("/api/materials", get_materials_api)

    # CSS / JS / assets
    app.router.add_static("/static", STATIC_DIR)

    return app


async def start_web_server(bot_token: str) -> None:
    """aiohttp web serverni ishga tushiradi (bot bilan parallel).
    
    Railway deploy uchun: web server DB init'dan OLDIN bind qilishi kerak,
    aks holda health check muvaffaqiyatsiz bo'ladi.
    """
    port = int(os.getenv("PORT", "8080"))
    app = create_app(bot_token)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"Web server started on 0.0.0.0:{port}")
    # Runner ni global saqlaymiz, graceful shutdown uchun
    return runner
