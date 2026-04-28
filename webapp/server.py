import os
import json
import hmac
import hashlib
import logging
from urllib.parse import parse_qsl

from aiohttp import web
import psycopg2.extras

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
    user = validate_telegram_init_data(init_data, bot_token)

    if not user:
        # Debug rejimida query param orqali ham ishlaydi
        debug = os.getenv("WEBAPP_DEBUG", "")
        if debug:
            try:
                user_id = int(request.rel_url.query.get("user_id", 0))
            except ValueError:
                return web.json_response({"error": "Invalid user_id"}, status=400)
        else:
            return web.json_response({"error": "Unauthorized"}, status=401)
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
                  AND t.user_id != %s
                ORDER BY tn.talaba_kod, tn.test_sanasi DESC
            ) sub
            WHERE sub.umumiy_ball > COALESCE(
                (SELECT umumiy_ball FROM test_natijalari
                 WHERE talaba_kod = %s ORDER BY test_sanasi DESC LIMIT 1), 0
            )
            """,
            (talaba["sinf"], user_id, talaba["kod"]),
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
            },
            headers={"Access-Control-Allow-Origin": "*"},
        )

    except Exception as e:
        logging.error(f"Student API error: {e}")
        return web.json_response({"error": "Server error"}, status=500)


async def admin_handler(request: web.Request) -> web.Response:
    """Admin sahifasini qaytaradi."""
    html_path = os.path.join(STATIC_DIR, "admin.html")
    return web.FileResponse(html_path)

async def admin_stats_api(request: web.Request) -> web.Response:
    """Admin uchun statistik ma'lumotlarni JSON formatida qaytaradi."""
    from config import ADMIN_IDS
    from database import get_connection, release_connection

    bot_token = request.app["bot_token"]

    # Telegram initData tekshiruvi
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

    # Faqat adminlarga ruxsat beriladi
    if user_id not in ADMIN_IDS:
        return web.json_response({"error": "Sizda admin huquqi yo'q!"}, status=403)

    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 1. KPI Stats
        cur.execute("SELECT COUNT(*) as count FROM talabalar WHERE status = 'aktiv'")
        total_students = cur.fetchone()["count"]

        cur.execute("SELECT COUNT(*) as count FROM test_natijalari")
        total_tests = cur.fetchone()["count"]

        cur.execute("SELECT AVG(umumiy_ball) as avg FROM test_natijalari")
        row = cur.fetchone()
        school_avg = row["avg"] if row and row["avg"] is not None else 0

        # 2. Class Stats
        cur.execute(
            """
            SELECT t.sinf, AVG(tn.umumiy_ball) as avg_score
            FROM test_natijalari tn
            JOIN talabalar t ON tn.talaba_kod = t.kod
            GROUP BY t.sinf
            ORDER BY t.sinf ASC
            """
        )
        class_stats_raw = cur.fetchall()
        class_stats = [{"sinf": r["sinf"], "avg_score": float(r["avg_score"])} for r in class_stats_raw if r["sinf"]]

        # 3. Direction Stats
        cur.execute(
            """
            SELECT t.yonalish, AVG(tn.umumiy_ball) as avg_score
            FROM test_natijalari tn
            JOIN talabalar t ON tn.talaba_kod = t.kod
            GROUP BY t.yonalish
            ORDER BY avg_score DESC
            """
        )
        direction_stats_raw = cur.fetchall()
        direction_stats = [{"yonalish": r["yonalish"], "avg_score": float(r["avg_score"])} for r in direction_stats_raw]

        # 4. Subject Averages
        cur.execute(
            """
            SELECT 
                AVG(majburiy_ball) as majburiy_avg,
                AVG(asosiy_1_ball) as asosiy_1_avg,
                AVG(asosiy_2_ball) as asosiy_2_avg
            FROM test_natijalari
            """
        )
        sub_row = cur.fetchone()
        subject_stats = {
            "majburiy": float(sub_row["majburiy_avg"] or 0),
            "asosiy_1": float(sub_row["asosiy_1_avg"] or 0),
            "asosiy_2": float(sub_row["asosiy_2_avg"] or 0)
        }

        # 5. Top 30 Students (eng yaxshi natijasi bo'yicha)
        cur.execute(
            """
            SELECT t.kod, t.ismlar, t.sinf, t.yonalish, MAX(tn.umumiy_ball) as umumiy_ball
            FROM test_natijalari tn
            JOIN talabalar t ON tn.talaba_kod = t.kod
            GROUP BY t.kod, t.ismlar, t.sinf, t.yonalish
            ORDER BY umumiy_ball DESC
            LIMIT 30
            """
        )
        top_students_raw = cur.fetchall()
        top_students = [
            {
                "kod": r["kod"],
                "ismlar": r["ismlar"],
                "sinf": r["sinf"],
                "yonalish": r["yonalish"],
                "umumiy_ball": float(r["umumiy_ball"]) if r["umumiy_ball"] else 0
            } for r in top_students_raw
        ]

        cur.close()
        release_connection(conn)

        return web.json_response(
            {
                "kpi": {
                    "total_students": total_students,
                    "total_tests": total_tests,
                    "school_avg": float(school_avg)
                },
                "class_stats": class_stats,
                "direction_stats": direction_stats,
                "subject_stats": subject_stats,
                "top_students": top_students
            },
            headers={"Access-Control-Allow-Origin": "*"},
        )

    except Exception as e:
        logging.error(f"Admin API error: {e}")
        return web.json_response({"error": "Server error"}, status=500)

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
        cur.execute("SELECT * FROM test_natijalari WHERE talaba_kod = %s ORDER BY sana ASC", (student_kod,))
        natijalar = cur.fetchall()
        
        # Format dates
        for n in natijalar:
            if n.get("sana"):
                n["sana"] = n["sana"].strftime("%Y-%m-%d")
        
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
            
        df = pd.read_sql(query, conn)
        release_connection(conn)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        
        output.seek(0)
        
        return web.Response(
            body=output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logging.error(f"Export API error: {e}")
        return web.json_response({"error": "Server error"}, status=500)


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
