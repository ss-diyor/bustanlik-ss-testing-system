import os
import json
import hmac
import hashlib
import logging
import asyncio
from urllib.parse import parse_qsl, quote
from html import escape
import re

from aiohttp import web
import psycopg2
import psycopg2.extras
from datetime import datetime
from config import MAJBURIY_KOEFF, ASOSIY_1_KOEFF, ASOSIY_2_KOEFF
from mock_admin_routes import register_mock_admin_routes
from mock_student_routes import register_mock_student_routes

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


async def student_cabinet_handler(request: web.Request) -> web.Response:
    """mock.sultanov.space dagi tasdiqlangan o'quvchi kabineti."""
    html_path = os.path.join(STATIC_DIR, "cabinet.html")
    return web.FileResponse(html_path)


def _mock_session_talaba_kod(request: web.Request) -> str | None:
    """Tashqi saytdagi Telegram-tasdiqlangan mock sessiyasini tekshiradi."""
    try:
        import mock_exam_engine
        return mock_exam_engine.session_talaba_kod(request.cookies.get("mock_session"))
    except Exception:
        return None


def _web_session_talaba(request: web.Request) -> dict | None:
    """Faqat tashqi saytda Telegram tasdiqlagan o'quvchini aniqlaydi."""
    kod = _mock_session_talaba_kod(request)
    if not kod:
        return None
    from database import get_connection, release_connection
    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            """
            SELECT t.*, COALESCE(m.nomi, '—') AS maktab_nomi
            FROM talabalar t LEFT JOIN maktablar m ON m.id=t.maktab_id
            WHERE t.kod=%s AND t.status='aktiv'
            """,
            (kod,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        cur.close(); release_connection(conn)


async def student_qr_api(request: web.Request) -> web.Response:
    talaba = _web_session_talaba(request)
    if not talaba:
        return web.json_response({"error": "Sessiya tugagan"}, status=401)
    from certificate import CertificateGenerator
    qr_buf = CertificateGenerator.from_db().generate_id_qr(talaba["kod"])
    return web.Response(
        body=qr_buf.getvalue(), content_type="image/png",
        headers={"Cache-Control": "no-store"},
    )


async def student_notification_settings_api(request: web.Request) -> web.Response:
    talaba = _web_session_talaba(request)
    if not talaba or not talaba.get("user_id"):
        return web.json_response({"error": "Sessiya tugagan"}, status=401)
    from database import get_notification_settings, update_notification_setting, NOTIFICATION_DEFAULTS
    if request.method == "GET":
        return web.json_response({"settings": get_notification_settings(talaba["user_id"])})
    try:
        data = await request.json()
        key = str(data.get("key", ""))
        enabled = bool(data.get("enabled"))
    except Exception:
        return web.json_response({"error": "Noto'g'ri so'rov"}, status=400)
    if key not in NOTIFICATION_DEFAULTS or not update_notification_setting(talaba["user_id"], key, enabled):
        return web.json_response({"error": "Sozlama yangilanmadi"}, status=400)
    return web.json_response({"success": True, "settings": get_notification_settings(talaba["user_id"])})


async def student_contact_admin_api(request: web.Request) -> web.Response:
    talaba = _web_session_talaba(request)
    if not talaba:
        return web.json_response({"error": "Sessiya tugagan"}, status=401)
    try:
        data = await request.json()
        message_text = str(data.get("message", "")).strip()
    except Exception:
        return web.json_response({"error": "Noto'g'ri so'rov"}, status=400)
    if not message_text or len(message_text) > 2000:
        return web.json_response({"error": "Xabar 1–2000 belgi oralig'ida bo'lishi kerak"}, status=400)

    from aiogram import Bot
    from config import ADMIN_IDS
    from keyboards import murojaat_javob_keyboard
    safe_message = escape(message_text)
    safe_name = escape(str(talaba.get("ismlar") or "—"))
    safe_school = escape(str(talaba.get("maktab_nomi") or "—"))
    text = (
        "📩 <b>Saytdan yangi murojaat</b>\n\n"
        f"🔑 <b>Kod:</b> <code>{escape(str(talaba['kod']))}</code>\n"
        f"👨‍🎓 <b>O'quvchi:</b> {safe_name}\n"
        f"🏫 <b>Maktab:</b> {safe_school}\n"
        f"📚 <b>Sinf:</b> {escape(str(talaba.get('sinf') or '—'))}\n\n"
        f"📝 <b>Murojaat:</b>\n{safe_message}"
    )
    bot = Bot(token=request.app["bot_token"])
    sent = False
    try:
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=murojaat_javob_keyboard(talaba["user_id"]))
                sent = True
            except Exception:
                continue
    finally:
        await bot.session.close()
    if not sent:
        return web.json_response({"error": "Adminga xabar yuborilmadi"}, status=503)
    return web.json_response({"success": True})


async def student_api(request: web.Request) -> web.Response:
    """O'quvchi ma'lumotlarini JSON formatida qaytaradi."""
    from database import get_connection, release_connection

    bot_token = request.app["bot_token"]

    # Telegram initData tekshiruvi
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, err_msg = validate_telegram_init_data(init_data, bot_token)

    session_kod = _mock_session_talaba_kod(request)
    if not user and not session_kod:
        # Debug rejimida query param orqali ham ishlaydi
        debug = os.getenv("WEBAPP_DEBUG", "")
        if debug:
            try:
                user_id = int(request.rel_url.query.get("user_id", 0))
            except ValueError:
                return web.json_response({"error": "Invalid user_id"}, status=400)
        else:
            return web.json_response({"error": f"Unauthorized: {err_msg}"}, status=401)
    elif user:
        user_id = user.get("id", 0)

    if session_kod:
        user_id = None

    if not user_id and not session_kod:
        return web.json_response({"error": "No user_id"}, status=400)

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # O'quvchi ma'lumotlari (real yoki demo sessiya orqali)
        if session_kod:
            cur.execute("""
                SELECT t.*, COALESCE(m.nomi, 'Noaniq maktab') as maktab_nomi
                FROM talabalar t LEFT JOIN maktablar m ON t.maktab_id = m.id
                WHERE t.kod = %s AND t.status = 'aktiv'
            """, (session_kod,))
        else:
            cur.execute("""
                SELECT t.*, COALESCE(m.nomi, 'Noaniq maktab') as maktab_nomi
                FROM talabalar t
                LEFT JOIN maktablar m ON t.maktab_id = m.id
                WHERE t.user_id = %s
            """, (user_id,))
        talaba = cur.fetchone()

        # Demo sessiyadan qidirish
        if not session_kod and (not talaba or talaba.get("is_demo")):
            cur.execute("""
                SELECT t.* FROM talabalar t
                JOIN demo_sessions d ON d.kod = t.kod
                WHERE d.user_id = %s AND t.is_demo = TRUE
            """, (user_id,))
            demo_talaba = cur.fetchone()
            if demo_talaba:
                talaba = demo_talaba

        if not talaba:
            cur.close()
            release_connection(conn)
            return web.json_response({"error": "Student not found"}, status=404)

        # Barcha natijalar (sanasi bo'yicha o'sib boruvchi tartib)
        cur.execute(
            """
            SELECT tn.id, tn.umumiy_ball, tn.majburiy, tn.asosiy_1,
                   tn.asosiy_2, tn.test_sanasi, cert.public_token
            FROM test_natijalari tn
            LEFT JOIN LATERAL (
                SELECT ps.public_token
                FROM public_sertifikatlar ps
                WHERE ps.natija_id = tn.id AND ps.revoked = FALSE
                ORDER BY ps.created_at DESC
                LIMIT 1
            ) cert ON TRUE
            WHERE tn.talaba_kod = %s
            ORDER BY tn.test_sanasi ASC
            """,
            (talaba["kod"],),
        )
        natijalar = cur.fetchall()

        # Sinf reytingi: shu maktab va sinfdagi har bir o'quvchining faqat
        # eng oxirgi DTM natijasi olinadi. Teng ballar bir xil o'rin oladi.
        cur.execute(
            """
            WITH latest AS (
                SELECT DISTINCT ON (t.kod)
                       t.kod, tn.umumiy_ball
                FROM test_natijalari tn
                JOIN talabalar t ON tn.talaba_kod = t.kod
                WHERE t.sinf = %s AND t.status = 'aktiv'
                  AND t.maktab_id IS NOT DISTINCT FROM %s
                ORDER BY t.kod, tn.test_sanasi DESC, tn.id DESC
            ), ranked AS (
                SELECT kod,
                       RANK() OVER (ORDER BY umumiy_ball DESC) AS sinf_rank
                FROM latest
            )
            SELECT ranked.sinf_rank,
                   (SELECT COUNT(*) FROM latest) AS sinf_total
            FROM (SELECT 1) seed
            LEFT JOIN ranked ON ranked.kod = %s
            """,
            (talaba["sinf"], talaba.get("maktab_id"), talaba["kod"]),
        )
        rank_row = cur.fetchone()
        sinf_rank = rank_row["sinf_rank"] if rank_row and rank_row["sinf_rank"] else "—"
        sinf_rank_total = int(rank_row["sinf_total"] or 0) if rank_row else 0

        # Sinfdoshlar ro'yxati (Faqat ismlar, maxfiylik uchun)
        # Faqat shu o'quvchining maktabi va sinfidagilar ko'rsatiladi.
        cur.execute(
            """
            SELECT ismlar
            FROM talabalar
            WHERE sinf = %s AND status = 'aktiv'
              AND maktab_id IS NOT DISTINCT FROM %s
            ORDER BY ismlar ASC
            """,
            (talaba["sinf"], talaba.get("maktab_id"))
        )
        classmates = cur.fetchall()

        cur.close()

        results_list = [
            {
                "id": n["id"],
                "umumiy_ball": float(n["umumiy_ball"]),
                "majburiy": float(n["majburiy"]),
                "asosiy_1": float(n["asosiy_1"]),
                "asosiy_2": float(n["asosiy_2"]),
                "sana": n["test_sanasi"].strftime("%d.%m.%Y") if n["test_sanasi"] else "—",
                "certificate_url": (
                    f"/cert/{n['public_token']}" if n.get("public_token") else None
                ),
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
                    "maktab": talaba.get("maktab_nomi", "Noma'lum maktab"),
                    "yonalish": talaba["yonalish"],
                },
                "stats": {
                    "avg": avg,
                    "best": best,
                    "total_tests": len(balls),
                    "trend": trend,
                    "sinf_rank": sinf_rank,
                    "sinf_rank_total": sinf_rank_total,
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
    finally:
        if conn:
            release_connection(conn)


def _generate_student_certificate(talaba: dict, natija: dict) -> tuple[str, str]:
    """DTM natijasi uchun public sertifikat yaratib, URL va hash qaytaradi."""
    from certificate import CertificateGenerator
    from database import sertifikat_public_saqlash

    sana = str(natija.get("test_sanasi") or "")[:10]
    generator = CertificateGenerator.from_db()
    pdf_path, cert_hash = generator.generate(
        talaba.get("ismlar", ""),
        natija.get("umumiy_ball", 0),
        sana,
        talaba.get("kod", ""),
        sinf=talaba.get("sinf", ""),
        maktab=talaba.get("maktab_nomi", "—"),
    )
    preview_path = generator.generate_preview(pdf_path)
    with open(pdf_path, "rb") as pdf_file:
        pdf_data = pdf_file.read()
    preview_data = None
    if preview_path and os.path.exists(preview_path):
        with open(preview_path, "rb") as preview_file:
            preview_data = preview_file.read()

    token = sertifikat_public_saqlash(
        certificate_hash=cert_hash,
        talaba_kod=talaba["kod"],
        natija_id=natija["id"],
        ismlar=talaba.get("ismlar", ""),
        maktab=talaba.get("maktab_nomi", "—"),
        sinf=talaba.get("sinf", ""),
        yonalish=talaba.get("yonalish", ""),
        umumiy_ball=natija["umumiy_ball"],
        majburiy=natija["majburiy"],
        asosiy_1=natija["asosiy_1"],
        asosiy_2=natija["asosiy_2"],
        test_sanasi=natija.get("test_sanasi"),
        pdf_data=pdf_data,
        preview_data=preview_data,
    )
    return f"/cert/{token}", cert_hash


async def student_dtm_certificate_api(request: web.Request) -> web.Response:
    """Tasdiqlangan o'quvchiga faqat o'z DTM sertifikatini yaratadi."""
    talaba = _web_session_talaba(request)
    if not talaba:
        return web.json_response({"error": "Sessiya tugagan"}, status=401)
    try:
        data = await request.json()
        result_id = int(data.get("result_id", 0))
    except (TypeError, ValueError, json.JSONDecodeError):
        return web.json_response({"error": "Natija noto'g'ri"}, status=400)
    if result_id <= 0:
        return web.json_response({"error": "Natija noto'g'ri"}, status=400)

    from database import get_connection, release_connection
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT tn.*, t.ismlar, t.sinf, t.yonalish,
                   COALESCE(m.nomi, '—') AS maktab_nomi
            FROM test_natijalari tn
            JOIN talabalar t ON t.kod = tn.talaba_kod
            LEFT JOIN maktablar m ON m.id = t.maktab_id
            WHERE tn.id = %s AND tn.talaba_kod = %s AND t.status = 'aktiv'
            """,
            (result_id, talaba["kod"]),
        )
        natija = cur.fetchone()
        if not natija:
            return web.json_response({"error": "Natija topilmadi"}, status=404)
        cur.execute(
            """
            SELECT public_token FROM public_sertifikatlar
            WHERE natija_id = %s AND talaba_kod = %s AND revoked = FALSE
            ORDER BY created_at DESC LIMIT 1
            """,
            (result_id, talaba["kod"]),
        )
        existing = cur.fetchone()
        if existing:
            return web.json_response({"certificate_url": f"/cert/{existing['public_token']}"})
        cert_student = {
            "kod": talaba["kod"], "ismlar": natija["ismlar"],
            "sinf": natija["sinf"], "yonalish": natija["yonalish"],
            "maktab_nomi": natija["maktab_nomi"],
        }
        result_data = dict(natija)
    finally:
        cur.close()
        release_connection(conn)

    try:
        certificate_url, cert_hash = await asyncio.to_thread(
            _generate_student_certificate, cert_student, result_data
        )
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE talabalar SET cert_hash = %s WHERE kod = %s",
                (cert_hash, talaba["kod"]),
            )
            conn.commit()
            cur.close()
        finally:
            release_connection(conn)
        return web.json_response({"certificate_url": certificate_url})
    except Exception:
        logging.exception("Kabinet DTM sertifikatini yaratishda xato")
        return web.json_response({"error": "Sertifikat yaratilmadi"}, status=500)


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


async def scanner_handler(request: web.Request) -> web.Response:
    """QR-kod skaner sahifasini qaytaradi."""
    html_path = os.path.join(STATIC_DIR, "scanner.html")
    return web.FileResponse(html_path)


async def attendance_record_api(request: web.Request) -> web.Response:
    """QR-kod orqali o'quvchi davomatini qaydga oladi. POST { kod: "..." }"""
    from database import get_connection, release_connection

    bot_token = request.app["bot_token"]

    # Telegram initData tekshiruvi
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, err_msg = validate_telegram_init_data(init_data, bot_token)

    session_kod = _mock_session_talaba_kod(request)
    if not user and not session_kod:
        debug = os.getenv("WEBAPP_DEBUG", "")
        if debug:
            try:
                admin_id = int(request.rel_url.query.get("user_id", 0))
            except ValueError:
                return web.json_response({"error": "Invalid user_id"}, status=400)
        else:
            return web.json_response({"error": f"Unauthorized: {err_msg}"}, status=401)
    else:
        admin_id = user.get("id", 0)

    # JSON body olish
    try:
        body = await request.json()
        kod = body.get("kod", "").strip()
    except Exception:
        return web.json_response({"error": "JSON body noto'g'ri"}, status=400)

    if not kod:
        return web.json_response({"error": "kod maydoni bo'sh"}, status=400)

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # O'quvchini kod bo'yicha topish
        cur.execute("""
            SELECT t.ismlar, t.kod, t.sinf, t.yonalish,
                   COALESCE(m.nomi, '') AS maktab_nomi
            FROM talabalar t
            LEFT JOIN maktablar m ON t.maktab_id = m.id
            WHERE t.kod = %s
        """, (kod,))
        talaba = cur.fetchone()

        if not talaba:
            cur.close()
            release_connection(conn)
            return web.json_response({"error": f"Kod topilmadi: {kod}"}, status=404)

        # Davomatni qaydga olish
        cur.execute("""
            INSERT INTO attendance (student_kod, admin_id, status, type)
            VALUES (%s, %s, 'present', 'qr_scan')
            RETURNING timestamp
        """, (kod, admin_id))
        row = cur.fetchone()
        timestamp = row["timestamp"]
        conn.commit()
        cur.close()
        release_connection(conn)

        return safe_json_response({
            "success": True,
            "student": {
                "ismlar": talaba["ismlar"],
                "kod": talaba["kod"],
                "sinf": talaba["sinf"] or "—",
                "maktab": talaba["maktab_nomi"] or "—",
                "yonalish": talaba["yonalish"] or "—",
            },
            "timestamp": timestamp,
        })

    except Exception as e:
        logging.error(f"attendance_record_api error: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
            release_connection(conn)
        return web.json_response({"error": "Server xatosi"}, status=500)


async def attendance_today_count_api(request: web.Request) -> web.Response:
    """Bugungi davomat sonini qaytaradi. GET -> { count: N }"""
    from database import get_connection, release_connection

    bot_token = request.app["bot_token"]

    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, err_msg = validate_telegram_init_data(init_data, bot_token)

    if not user:
        debug = os.getenv("WEBAPP_DEBUG", "")
        if not debug:
            return web.json_response({"error": f"Unauthorized: {err_msg}"}, status=401)

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE timestamp::date = CURRENT_DATE
        """)
        count = cur.fetchone()[0]
        cur.close()
        release_connection(conn)
        return web.json_response({"count": count})

    except Exception as e:
        logging.error(f"attendance_today_count_api error: {e}")
        if conn:
            release_connection(conn)
        return web.json_response({"error": "Server xatosi"}, status=500)


async def get_user_role(user_id, conn):
    """Foydalanuvchi rolini aniqlaydi (admin yoki oqituvchi)."""
    from config import ADMIN_IDS
    if user_id in ADMIN_IDS:
        return "admin", None

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # admins jadvalini tekshirish
    cur.execute("SELECT user_id FROM admins WHERE user_id = %s", (user_id,))
    if cur.fetchone():
        cur.close()
        return "admin", None

    # oqituvchilar jadvalini tekshirish
    cur.execute("SELECT sinf FROM oqituvchilar WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    cur.close()
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
    elif user:
        user_id = user.get("id", 0)

    if session_kod:
        user_id = None

    conn = get_connection()
    try:
        role, teacher_sinf = await get_user_role(user_id, conn)
    finally:
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

    conn = None
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
        class_stats = [{"sinf": r["sinf"], "avg_score": float(r["avg_score"] or 0)} for r in cur.fetchall() if r["sinf"]]

        # 3. Direction Stats (Filtered for teacher)
        if role == "admin":
            cur.execute("SELECT yonalish, AVG(umumiy_ball) as avg_score FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod GROUP BY t.yonalish ORDER BY avg_score DESC")
        else:
            cur.execute("SELECT yonalish, AVG(umumiy_ball) as avg_score FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod WHERE t.sinf = %s GROUP BY t.yonalish ORDER BY avg_score DESC", [teacher_sinf])
        direction_stats = [{"yonalish": r["yonalish"], "avg_score": float(r["avg_score"] or 0)} for r in cur.fetchall()]

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
            cur.execute("SELECT t.kod, t.ismlar, t.sinf, t.yonalish, COALESCE(m.nomi, 'Noma\'lum maktab') as maktab_nomi, MAX(tn.umumiy_ball) as ball FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod LEFT JOIN maktablar m ON t.maktab_id = m.id GROUP BY t.kod, t.ismlar, t.sinf, t.yonalish, m.nomi ORDER BY ball DESC LIMIT 30")
        else:
            cur.execute("SELECT t.kod, t.ismlar, t.sinf, t.yonalish, COALESCE(m.nomi, 'Noma\'lum maktab') as maktab_nomi, MAX(tn.umumiy_ball) as ball FROM test_natijalari tn JOIN talabalar t ON tn.talaba_kod = t.kod LEFT JOIN maktablar m ON t.maktab_id = m.id WHERE t.sinf = %s GROUP BY t.kod, t.ismlar, t.sinf, t.yonalish, m.nomi ORDER BY ball DESC LIMIT 30", [teacher_sinf])
        top_students = [{"kod": r["kod"], "ismlar": r["ismlar"], "sinf": r["sinf"], "maktab": r.get("maktab_nomi", "Noma'lum maktab"), "yonalish": r["yonalish"], "umumiy_ball": float(r["ball"] or 0)} for r in cur.fetchall()]

        cur.close()

        return web.json_response({
            "role": role,
            "teacher_sinf": teacher_sinf,
            "kpi": {"total_students": total_students, "total_tests": total_tests, "school_avg": float(school_avg)},
            "class_stats": class_stats,
            "direction_stats": direction_stats,
            "subject_stats": subject_stats,
            "top_students": top_students
        })
    except Exception as e:
        logging.error(f"Admin API error details: {e}", exc_info=True)
        return web.json_response({"error": f"Server xatosi: {str(e)}"}, status=500)
    finally:
        if conn:
            release_connection(conn)

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
        asyncio.create_task(run_broadcast(request.app["bot_token"], users, message_text))
        
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



async def student_mock_api(request: web.Request) -> web.Response:
    """O'quvchining mock imtihon natijalarini qaytaradi."""
    from database import get_connection, release_connection

    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, err_msg = validate_telegram_init_data(init_data, bot_token)

    session_kod = _mock_session_talaba_kod(request)
    if not user and not session_kod:
        debug = os.getenv("WEBAPP_DEBUG", "")
        if debug:
            try:
                user_id = int(request.rel_url.query.get("user_id", 0))
            except ValueError:
                return web.json_response({"error": "Invalid user_id"}, status=400)
        else:
            return web.json_response({"error": f"Unauthorized: {err_msg}"}, status=401)
    elif user:
        user_id = user.get("id", 0)

    if session_kod:
        user_id = None

    if not user_id and not session_kod:
        return web.json_response({"error": "No user_id"}, status=400)

    try:
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Talaba kodini topish (demo sessiyani ham qo'llab-quvvatlash)
        if session_kod:
            cur.execute("SELECT kod FROM talabalar WHERE kod = %s AND status = 'aktiv'", (session_kod,))
        else:
            cur.execute("SELECT kod FROM talabalar WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if not session_kod and not row:
            cur.execute("""
                SELECT t.kod FROM talabalar t
                JOIN demo_sessions d ON d.kod = t.kod
                WHERE d.user_id = %s AND t.is_demo = TRUE
            """, (user_id,))
            row = cur.fetchone()

        if not row:
            cur.close(); release_connection(conn)
            return web.json_response({"error": "Student not found"}, status=404)

        talaba_kod = row["kod"]

        # Mock natijalarini olish (so'nggi 50 ta, barcha imtihon turlari)
        cur.execute("""
            SELECT mn.id, mn.exam_key, mn.exam_label, mn.sections,
                   mn.umumiy_ball, mn.level_label, mn.subject_name,
                   mn.notes, mn.test_sanasi, et.total_max, et.score_type,
                   public_result.public_token
            FROM mock_natijalari mn
            LEFT JOIN mock_exam_types et ON et.exam_key = mn.exam_key
            LEFT JOIN LATERAL (
                SELECT pmn.public_token
                FROM public_mock_natijalar pmn
                WHERE pmn.mock_natija_id = mn.id AND pmn.revoked = FALSE
                LIMIT 1
            ) public_result ON TRUE
            WHERE mn.talaba_kod = %s
            ORDER BY mn.test_sanasi DESC
            LIMIT 50
        """, (talaba_kod,))
        rows = cur.fetchall()

        exam_keys = sorted({row["exam_key"] for row in rows})
        section_configs = {}
        if exam_keys:
            cur.execute(
                """
                SELECT exam_key, section_key, label, max_score
                FROM mock_sections
                WHERE exam_key = ANY(%s)
                ORDER BY exam_key, sort_order, id
                """,
                (exam_keys,),
            )
            for section in cur.fetchall():
                section_configs.setdefault(section["exam_key"], []).append({
                    "key": section["section_key"],
                    "label": section["label"],
                    "max_score": (
                        float(section["max_score"])
                        if section["max_score"] is not None else None
                    ),
                })

        cur.close(); release_connection(conn)

        import json as _json
        natijalar = []
        for r in rows:
            d = dict(r)
            if isinstance(d.get("sections"), str):
                d["sections"] = _json.loads(d["sections"])
            if d.get("test_sanasi"):
                d["test_sanasi"] = d["test_sanasi"].strftime("%d.%m.%Y")
            if d.get("umumiy_ball") is not None:
                d["umumiy_ball"] = float(d["umumiy_ball"])
            if d.get("total_max") is not None:
                d["total_max"] = float(d["total_max"])
            d["section_config"] = section_configs.get(d["exam_key"], [])
            d["verification_url"] = (
                f"/mock-cert/{d['public_token']}" if d.get("public_token") else None
            )
            d.pop("public_token", None)
            natijalar.append(d)

        return safe_json_response({"mock_results": natijalar})

    except Exception as e:
        logging.error(f"Student Mock API error: {e}", exc_info=True)
        return web.json_response({"error": "Server error"}, status=500)


def _student_mock_result(talaba_kod: str, result_id: int) -> dict | None:
    """Sessiyadagi o'quvchiga tegishli bitta mock natijani qaytaradi."""
    from database import get_connection, release_connection
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM mock_natijalari WHERE id=%s AND talaba_kod=%s",
            (result_id, talaba_kod),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        result = dict(row)
        if isinstance(result.get("sections"), str):
            result["sections"] = json.loads(result["sections"])
        return result
    finally:
        release_connection(conn)


async def student_mock_verification_api(request: web.Request) -> web.Response:
    """Mock natija uchun QR-tasdiqlash havolasini yaratadi yoki qaytaradi."""
    talaba = _web_session_talaba(request)
    if not talaba:
        return web.json_response({"error": "Sessiya tugagan"}, status=401)
    try:
        data = await request.json()
        result_id = int(data.get("result_id", 0))
    except Exception:
        return web.json_response({"error": "Natija noto'g'ri"}, status=400)
    result = _student_mock_result(talaba["kod"], result_id)
    if not result:
        return web.json_response({"error": "Natija topilmadi"}, status=404)
    try:
        from mock_database import mock_public_token_ol_yoki_yarat
        token = await asyncio.to_thread(
            mock_public_token_ol_yoki_yarat, talaba, result
        )
        if not token:
            raise RuntimeError("Token yaratilmadi")
        return web.json_response({"verification_url": f"/mock-cert/{token}"})
    except Exception:
        logging.exception("Mock tasdiqlash havolasini yaratishda xato")
        return web.json_response({"error": "Tasdiqlash havolasi yaratilmadi"}, status=500)


async def student_mock_report_pdf_api(request: web.Request) -> web.Response:
    """O'quvchining muayyan mock natijasini PDF hisobot sifatida qaytaradi."""
    talaba = _web_session_talaba(request)
    if not talaba:
        raise web.HTTPUnauthorized(text="Sessiya tugagan")
    try:
        result_id = int(request.match_info.get("result_id", "0"))
    except ValueError:
        raise web.HTTPBadRequest(text="Natija noto'g'ri")
    result = _student_mock_result(talaba["kod"], result_id)
    if not result:
        raise web.HTTPNotFound(text="Natija topilmadi")

    pdf_path = png_path = None
    try:
        from mock_report import generate_mock_report
        pdf_path, png_path = await asyncio.to_thread(
            generate_mock_report,
            talaba["kod"],
            result.get("exam_key"),
            result_id,
        )
        if not pdf_path or not os.path.exists(pdf_path):
            raise RuntimeError("PDF yaratilmadi")
        with open(pdf_path, "rb") as pdf_file:
            pdf_data = pdf_file.read()
        filename = f"mock_{talaba['kod']}_{result_id}.pdf"
        return web.Response(
            body=pdf_data,
            content_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )
    except web.HTTPException:
        raise
    except Exception:
        logging.exception("Kabinet mock PDF hisobotini yaratishda xato")
        return web.json_response({"error": "PDF hisobot yaratilmadi"}, status=500)
    finally:
        for path in (pdf_path, png_path):
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


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

    # Mock natijalarni olish
    mock_natijalar = []
    try:
        from mock_database import mock_natijalari_ol
        mock_natijalar = mock_natijalari_ol(kod, limit=5)
    except Exception as e:
        logging.error(f"Mock results fetch error: {e}")

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
        text=_verify_success_html(talaba, natija, stored_hash, hash_valid, mock_natijalar),
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


def _public_certificate_not_found() -> web.Response:
    return web.Response(
        status=404,
        content_type="text/html",
        text="""<!doctype html><html lang="uz"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sertifikat topilmadi</title><body style="margin:0;display:grid;place-items:center;min-height:100vh;font-family:system-ui;background:#f5f8ff;color:#16213e"><main style="max-width:360px;text-align:center;padding:32px"><div style="font-size:52px">🔎</div><h1>Sertifikat topilmadi</h1><p>Havola noto‘g‘ri yoki sertifikat bekor qilingan bo‘lishi mumkin.</p></main></body></html>""",
    )


def _public_certificate_record(request: web.Request) -> dict | None:
    token = request.match_info.get("token", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,100}", token):
        return None
    from database import sertifikat_public_ol
    return sertifikat_public_ol(token)


def _public_mock_result_record(request: web.Request) -> dict | None:
    token = request.match_info.get("token", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,100}", token):
        return None
    from mock_database import mock_public_natija_ol
    return mock_public_natija_ol(token)


async def public_mock_result_handler(request: web.Request) -> web.Response:
    """Mock hisobotidagi QR-kod uchun minimal, tasdiqlovchi public sahifa."""
    record = _public_mock_result_record(request)
    if not record:
        return _public_certificate_not_found()

    from config import CERTIFICATE_BASE_URL, BOT_USERNAME

    token = record["public_token"]
    public_url = f"{CERTIFICATE_BASE_URL}/mock-cert/{token}"
    student_name = escape(str(record.get("ismlar") or "O'quvchi"))
    subject = escape(str(record.get("subject_name") or record.get("exam_label") or "—"))
    level = escape(str(record.get("level_label") or "—"))
    score = record.get("umumiy_ball")
    score_text = f"{score:g}" if isinstance(score, (int, float)) else "—"
    test_date = record.get("test_sanasi")
    date_text = test_date.strftime("%d.%m.%Y") if test_date else "—"
    bot_username = (BOT_USERNAME or "bustanlik_ss_bot").lstrip("@")
    # Nisbiy URL ishlatiladi: QR sahifasi qaysi domenda ochilsa, logo ham aynan
    # o'sha domendan yuklanadi (VERIFY_BASE_URL noto'g'ri bo'lsa ham).
    logo_url = "/static/logo.png"
    title = f"{student_name} — Mock natijasi tasdiqlanishi"

    page = f"""<!doctype html>
<html lang="uz"><head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="Bo'stonliq SS Testing System mock natijasi tasdiqlanishi">
  <meta property="og:type" content="website"><meta property="og:title" content="{title}">
  <meta property="og:description" content="Mock natijasi tizimda tasdiqlangan.">
  <meta property="og:url" content="{escape(public_url)}">
  <style>
    :root {{ --navy:#1c2864; --ink:#252942; --muted:#62677c; --line:#d9ddeb; --green:#439b34; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; min-height:100vh; background:#f5f6fa; color:var(--ink); font-family:Inter,"Segoe UI",system-ui,sans-serif; }}
    .page {{ width:min(100%,760px); margin:0 auto; padding:46px 18px; }}
    .report {{ background:#fff; border:1px solid var(--line); box-shadow:0 12px 36px rgba(20,30,80,.10); }}
    .top {{ padding:28px 28px 24px; text-align:center; }} .school-logo {{ display:block; width:112px; height:112px; margin:0 auto; object-fit:contain; }}
    .band {{ background:var(--navy); color:#fff; text-align:center; padding:23px 20px 21px; }}
    .band h1 {{ font-size:clamp(1.3rem,4vw,1.85rem); letter-spacing:.05em; margin:0; }} .band p {{ margin:7px 0 0; font-size:.93rem; letter-spacing:.08em; }}
    .body {{ padding:34px 34px 30px; }} .valid {{ display:inline-flex; align-items:center; gap:8px; color:#287c24; background:#eef9ed; border:1px solid #b7dfb4; border-radius:999px; padding:8px 13px; font-size:.9rem; font-weight:750; }}
    h2 {{ color:var(--navy); font-size:clamp(1.35rem,4vw,1.8rem); margin:23px 0 7px; }} .intro {{ color:var(--muted); margin:0 0 24px; }}
    .rows {{ border-top:1px solid var(--line); }} .row {{ display:flex; justify-content:space-between; gap:20px; padding:15px 0; border-bottom:1px solid var(--line); }} .label {{ color:var(--muted); }} .value {{ margin-left:12px; font-weight:750; text-align:right; }}
    .result {{ display:flex; align-items:center; justify-content:space-between; gap:20px; padding:20px; margin-top:25px; color:#fff; background:var(--navy); }} .result small {{ display:block; opacity:.78; margin-bottom:4px; }} .result strong {{ font-size:1.65rem; }}
    footer {{ margin-top:34px; padding-top:17px; border-top:1px solid var(--line); color:var(--muted); font-size:.9rem; }} footer a {{ color:var(--navy); font-weight:700; text-decoration:none; }}
    @media (max-width:520px) {{ .page {{ padding:18px 10px; }} .top {{ padding:28px 18px 24px; }} .body {{ padding:25px 20px; }} .row {{ display:block; }} .value {{ text-align:left; margin:5px 0 0; }} }}
  </style>
</head><body><main class="page"><article class="report">
  <header class="top"><img src="{escape(logo_url)}" class="school-logo" alt="Maktab logosi"></header>
  <section class="band"><h1>MOCK NATIJASI</h1><p>NATIJANI TASDIQLASH</p></section>
  <section class="body"><div class="valid">✓ Mock natijasi haqiqiy</div>
    <h2>{student_name}</h2><p class="intro">Quyidagi mock imtihon natijasi tizimda tasdiqlangan.</p>
    <div class="rows"><div class="row"><span class="label">Fan:&nbsp;</span><span class="value">{subject}</span></div><div class="row"><span class="label">Daraja:&nbsp;</span><span class="value">{level}</span></div><div class="row"><span class="label">Natija sanasi:&nbsp;</span><span class="value">{date_text}</span></div></div>
    <div class="result"><div><small>UMUMIY BALL</small><strong>{score_text}</strong></div><div>✓ TASDIQLANGAN</div></div>
    <footer><a href="https://t.me/{escape(bot_username)}" target="_blank" rel="noopener">@{escape(bot_username)}</a></footer>
  </section>
</article></main></body></html>"""
    return web.Response(content_type="text/html", text=page)


async def public_certificate_pdf_handler(request: web.Request) -> web.Response:
    record = _public_certificate_record(request)
    if not record:
        return _public_certificate_not_found()

    pdf_data = record.get("pdf_data")
    if not pdf_data:
        return _public_certificate_not_found()
    return web.Response(
        body=bytes(pdf_data),
        content_type="application/pdf",
        headers={
            "Content-Disposition": 'inline; filename="sertifikat.pdf"',
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


async def public_certificate_preview_handler(request: web.Request) -> web.Response:
    record = _public_certificate_record(request)
    if not record or not record.get("preview_data"):
        return _public_certificate_not_found()
    return web.Response(
        body=bytes(record["preview_data"]),
        content_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


async def public_certificate_handler(request: web.Request) -> web.Response:
    """Token asosidagi, PDF preview va social share tugmali sertifikat sahifasi."""
    record = _public_certificate_record(request)
    if not record:
        return _public_certificate_not_found()

    from config import CERTIFICATE_BASE_URL

    token = record["public_token"]
    public_url = f"{CERTIFICATE_BASE_URL}/cert/{token}"
    pdf_url = f"{public_url}/file.pdf"
    preview_url = f"{public_url}/preview.png"
    student_name = escape(str(record.get("ismlar") or "O‘quvchi"))
    school = escape(str(record.get("maktab") or "—"))
    score = record.get("umumiy_ball", "—")
    test_date = record.get("test_sanasi")
    date_text = test_date.strftime("%d.%m.%Y") if test_date else "—"
    title = f"{student_name} — {score} ball | DTM sertifikati"
    share_text = f"DTM natijam: {score} ball. Sertifikatni ko‘ring."
    encoded_url = quote(public_url, safe="")
    telegram_url = f"https://t.me/share/url?url={encoded_url}&text={quote(share_text, safe='')}"
    whatsapp_url = f"https://wa.me/?text={quote(share_text + ' ' + public_url, safe='')}"
    linkedin_url = f"https://www.linkedin.com/sharing/share-offsite/?url={encoded_url}"
    og_image = (
        f'<meta property="og:image" content="{escape(preview_url)}">'
        if record.get("preview_data") else ""
    )

    page = f"""<!doctype html>
<html lang="uz">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="Bo‘stonliq ITMA DTM natijalari sertifikati">
  <meta property="og:type" content="website">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="Bo‘stonliq ITMA — DTM natijalari sertifikati">
  <meta property="og:url" content="{escape(public_url)}">
  {og_image}
  <style>
    :root {{ color-scheme: light; --blue:#315de8; --ink:#13213f; --muted:#60708e; --line:#dde5f3; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif; background:#f4f7fc; color:var(--ink); }}
    .page {{ max-width:980px; margin:auto; padding:24px 16px 40px; }}
    .head {{ display:flex; gap:14px; align-items:center; margin-bottom:18px; }}
    .seal {{ width:48px; height:48px; display:grid; place-items:center; border-radius:14px; background:linear-gradient(135deg,#315de8,#6f8cff); color:white; font-size:25px; }}
    h1 {{ font-size:clamp(1.15rem,4vw,1.55rem); margin:0; }} .sub {{ color:var(--muted); margin:4px 0 0; font-size:.92rem; }}
    .card {{ background:#fff; border:1px solid var(--line); border-radius:18px; padding:18px; box-shadow:0 8px 28px rgba(31,62,119,.08); }}
    .summary {{ display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap; align-items:center; margin-bottom:16px; }}
    .name {{ font-weight:800; font-size:1.15rem; }} .meta {{ color:var(--muted); margin-top:4px; }}
    .score {{ color:var(--blue); font-weight:800; font-size:1.2rem; white-space:nowrap; }}
    .actions {{ display:flex; flex-wrap:wrap; gap:9px; margin:0 0 16px; }}
    .btn {{ border:0; border-radius:10px; padding:10px 13px; font:inherit; font-weight:700; cursor:pointer; text-decoration:none; background:#edf2ff; color:#244fcf; }}
    .btn.primary {{ background:var(--blue); color:white; }}
    .pdf {{ width:100%; height:min(78vh,900px); border:1px solid var(--line); border-radius:12px; background:#eef2f8; }}
    .notice {{ margin:14px 0 0; color:var(--muted); font-size:.84rem; text-align:center; }}
    @media (max-width:540px) {{ .page {{ padding:16px 10px 28px; }} .card {{ padding:12px; }} .pdf {{ height:72vh; }} .btn {{ flex:1; text-align:center; }} }}
  </style>
</head>
<body><main class="page">
  <header class="head"><div class="seal">✓</div><div><h1>DTM natijalari sertifikati</h1><p class="sub">✅ Sertifikat haqiqiy va tizimda tasdiqlangan</p></div></header>
  <section class="card">
    <div class="summary"><div><div class="name">{student_name}</div><div class="meta">{school} · {date_text}</div></div><div class="score">{score} / 189 ball</div></div>
    <nav class="actions" aria-label="Sertifikat amallari">
      <a class="btn primary" href="{escape(pdf_url)}" download>⬇️ PDF yuklab olish</a>
      <button class="btn" type="button" onclick="shareCertificate()">🔗 Ulashish</button>
      <a class="btn" href="{telegram_url}" target="_blank" rel="noopener">Telegram</a>
      <a class="btn" href="{whatsapp_url}" target="_blank" rel="noopener">WhatsApp</a>
      <a class="btn" href="{linkedin_url}" target="_blank" rel="noopener">LinkedIn</a>
    </nav>
    <iframe class="pdf" title="DTM natijalari sertifikati PDF" src="{escape(pdf_url)}#view=FitH"><a href="{escape(pdf_url)}">PDF sertifikatni oching</a></iframe>
    <p class="notice">Instagram Story uchun PDF’ni yuklab olib, Instagram ilovasidan ulashing.</p>
  </section>
</main>
<script>
  async function shareCertificate() {{
    const shareData = {{ title: 'DTM natijalari sertifikati', text: '{share_text}', url: '{public_url}' }};
    if (navigator.share) {{ try {{ await navigator.share(shareData); return; }} catch (_) {{}} }}
    await navigator.clipboard?.writeText(shareData.url);
    alert('Sertifikat havolasi nusxalandi.');
  }}
</script></body></html>"""
    return web.Response(content_type="text/html", text=page)


_VERIFY_CSS = """
:root {
  --primary: #1a5276;
  --primary-light: #2980b9;
  --accent: #16a085;
  --text: #1a202c;
  --muted: #5a6a7a;
  --border: #e2e8f0;
  --success: #1e8449;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: #f5f7fa;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 16px;
}
.wrapper { width: 100%; max-width: 460px; }
.card {
  background: #fff;
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0,0,0,.08);
}
.header-band {
  background: #fff;
  padding: 32px 24px 8px;
  text-align: center;
}
.school-logo {
  width: 130px; height: 130px;
  object-fit: contain;
}
.logo-placeholder {
  width: 100px; height: 100px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 3em;
}
.school-name { display: none; }
.body { padding: 8px 28px 28px; text-align: center; }
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
  color: #1a2d6b;
  line-height: 1;
}
.score-max { font-size: .38em; color: #1a2d6b; font-weight: 400; opacity: 0.6; }
.score-pct {
  color: #1a2d6b;
  font-weight: 700;
  font-size: 1em;
  margin: 4px 0 14px;
  opacity: 0.75;
}
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
}
.hash-value {
  font-family: 'Courier New', monospace;
  font-size: .68em;
  color: #4a5568;
  word-break: break-all;
  line-height: 1.5;
}
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
.footer-hint { font-size: .75em; color: var(--muted); }
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
}
.tg-link svg { width: 15px; height: 15px; fill: #fff; }
.no-result { color: #a0aec0; font-style: italic; padding: 16px 0; }
.mock-section { margin-top: 24px; text-align: left; }
.section-title { font-size: .85em; font-weight: 700; color: var(--muted); margin-bottom: 12px; text-transform: uppercase; letter-spacing: .05em; }
.mock-list { display: none; flex-direction: column; gap: 8px; margin-top: 12px; }
.mock-item { background: #f8fafc; border: 1px solid #edf2f7; border-radius: 12px; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; }
.mock-info { display: flex; flex-direction: column; }
.mock-name { font-size: .9em; font-weight: 700; color: var(--text); }
.mock-date { font-size: .75em; color: var(--muted); }
.mock-score { font-size: 1.2em; font-weight: 800; color: var(--primary); }
.toggle-mock-btn {
  width: 100%;
  background: #fff;
  border: 1px solid var(--primary-light);
  color: var(--primary-light);
  padding: 10px;
  border-radius: 12px;
  font-size: .85em;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: all 0.2s;
}
.toggle-mock-btn:hover { background: #f0f7ff; }
.toggle-mock-btn svg { width: 16px; height: 16px; fill: currentColor; transition: transform 0.2s; }
.toggle-mock-btn.active svg { transform: rotate(180deg); }
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
                         cert_hash: str = "", hash_valid: bool = True,
                         mock_natijalar: list = None) -> str:
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

    # Mock natijalar bloki
    mock_blok = ""
    if mock_natijalar:
        mock_items = ""
        for m in mock_natijalar:
            m_ball = m.get("umumiy_ball", 0)
            m_sana = str(m.get("test_sanasi", ""))[:10]
            m_nomi = m.get("exam_key", "Mock")
            mock_items += f"""
            <div class="mock-item">
              <div class="mock-info">
                <span class="mock-name">🎯 {m_nomi}</span>
                <span class="mock-date">{m_sana}</span>
              </div>
              <div class="mock-score">{m_ball}</div>
            </div>"""
        
        mock_blok = f"""
        <div class="mock-section">
          <button class="toggle-mock-btn" onclick="toggleMockResults()">
            🎯 Mock imtihon natijalari
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M7 10l5 5 5-5z"/></svg>
          </button>
          <div id="mockList" class="mock-list">
            <div class="section-title" style="margin-top: 15px; margin-bottom: 8px;">So'nggi natijalar</div>
            {mock_items}
          </div>
        </div>
        <script>
          function toggleMockResults() {{
            const list = document.getElementById('mockList');
            const btn = document.querySelector('.toggle-mock-btn');
            if (list.style.display === 'flex') {{
              list.style.display = 'none';
              btn.classList.remove('active');
            }} else {{
              list.style.display = 'flex';
              btn.classList.add('active');
            }}
          }}
        </script>"""

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
      <div class="school-name">Bo'stonliq tumani ixtisoslashtirilgan maktabi</div>
    </div>

    <div class="body">
      {badge_html}
      <div class="student-name">{ism}</div>
      <div class="student-meta">{sinf}<span class="sep">|</span>{yo}</div>

      {natija_blok}

      {mock_blok}

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
    app.router.add_get("/cabinet", student_cabinet_handler)
    app.router.add_get("/cabinet/{section}", student_cabinet_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/verify/{kod}", verify_handler)
    app.router.add_get("/scan/{kod}", verify_handler)  # QR-kod uchun alias
    app.router.add_get("/cert/{token}", public_certificate_handler)
    app.router.add_get("/cert/{token}/file.pdf", public_certificate_pdf_handler)
    app.router.add_get("/cert/{token}/preview.png", public_certificate_preview_handler)
    app.router.add_get("/mock-cert/{token}", public_mock_result_handler)
    app.router.add_get("/api/student", student_api)
    app.router.add_post("/api/student/dtm/certificate", student_dtm_certificate_api)
    app.router.add_get("/api/student/mock", student_mock_api)
    app.router.add_post("/api/student/mock/verification", student_mock_verification_api)
    app.router.add_get("/api/student/mock/report/{result_id}.pdf", student_mock_report_pdf_api)
    app.router.add_get("/api/student/qr", student_qr_api)
    app.router.add_get("/api/student/notifications", student_notification_settings_api)
    app.router.add_put("/api/student/notifications", student_notification_settings_api)
    app.router.add_post("/api/student/contact-admin", student_contact_admin_api)
    
    app.router.add_get("/admin", admin_handler)
    app.router.add_get("/scanner", scanner_handler)
    app.router.add_post("/api/attendance/record", attendance_record_api)
    app.router.add_get("/api/attendance/today-count", attendance_today_count_api)
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

    # Mock imtihon — kerakli funksiyalarni app obyektiga ulaymiz
    # ('from server import ...' server.py asosiy fayl bo'lgani uchun ishlamaydi —
    # u __main__ deb yuklanadi, 'server' nomli modul sifatida emas)
    app["check_admin_role"] = check_admin_role
    app["validate_telegram_init_data"] = validate_telegram_init_data

    # Mock imtihon — savollar boshqaruvi (admin) va onlayn topshirish (talaba)
    register_mock_admin_routes(app)
    register_mock_student_routes(app)

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
