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

def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """
    Telegram WebApp initData ni kriptografik tekshiradi.
    Muvaffaqiyatli bo'lsa user dict qaytaradi, aks holda None.
    """
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

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
            return None

        return json.loads(parsed.get("user", "{}"))
    except Exception as e:
        logging.warning(f"initData validation error: {e}")
        return None


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
            },
            headers={"Access-Control-Allow-Origin": "*"},
        )

    except Exception as e:
        logging.error(f"Student API error: {e}")
        return web.json_response({"error": "Server error"}, status=500)


# ─────────────────────────────────────────
# App factory
# ─────────────────────────────────────────

def create_app(bot_token: str) -> web.Application:
    app = web.Application()
    app["bot_token"] = bot_token

    app.router.add_get("/", index_handler)
    app.router.add_get("/api/student", student_api)

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
