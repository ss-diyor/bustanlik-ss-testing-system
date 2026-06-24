"""
Mock imtihon — TALABA API marshrutlari (jamoat sayti uchun: mock.sultanov.space).

Bu yerda talaba o'z kodi bilan kiradi (Telegram orqali emas), shuning uchun
autentifikatsiya alohida — httpOnly cookie ichidagi sessiya tokeni orqali.
"""

import os
import json
import logging
from aiohttp import web
from aiohttp.web import json_response as _aiohttp_json_response

import mock_exam_engine as engine

STATIC_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_COOKIE = "mock_session"


def _json(data, status=200):
    """web.json_response o'rnini bosadi — datetime maydonlarini xavfsiz serialize qiladi."""
    return _aiohttp_json_response(
        data, status=status, dumps=lambda d: json.dumps(d, default=str)
    )


# ─────────────────────────────────────────
# Domen asosida yo'naltirish
# ─────────────────────────────────────────
#
# Bitta Railway ilovasi bir nechta domenga (asosiy bot webapp + mock.sultanov.space)
# xizmat ko'rsatadi. Asosiy "/" route Telegram WebApp uchun mo'ljallangan va
# initData talab qiladi. mock.sultanov.space orqali kirilganda esa, "/" da
# mustaqil bosh sahifa (mock-landing.html) ko'rsatiladi — asosiy domenning
# ishlashiga tegmaymiz.

@web.middleware
async def mock_domain_redirect_middleware(request: web.Request, handler):
    host = request.host.split(":")[0].lower()
    if host.startswith("mock.") and request.path == "/":
        return web.FileResponse(os.path.join(STATIC_DIR, "mock-landing.html"))
    return await handler(request)


# ─────────────────────────────────────────
# Yordamchi
# ─────────────────────────────────────────

def _get_talaba_kod(request: web.Request):
    token = request.cookies.get(SESSION_COOKIE)
    return engine.session_talaba_kod(token)


def _unauthorized():
    return _json({"error": "Sessiya tugagan, qaytadan kiring"}, status=401)


# ─────────────────────────────────────────
# Login / Logout
# ─────────────────────────────────────────

async def mock_login_api(request: web.Request) -> web.Response:
    """POST { kod: 'SS001' } -> sessiya cookie o'rnatadi."""
    try:
        data = await request.json()
        kod = (data.get("kod") or "").strip()
    except Exception:
        return _json({"error": "Noto'g'ri so'rov"}, status=400)

    if not kod:
        return _json({"error": "Kodni kiriting"}, status=400)

    token, talaba = engine.talaba_login(kod)
    if not token:
        return _json({"error": "Kod topilmadi yoki faol emas"}, status=404)

    resp = _json({"success": True, "student": talaba})
    resp.set_cookie(
        SESSION_COOKIE, token,
        max_age=6 * 3600, httponly=True, samesite="Lax", secure=True,
    )
    return resp


async def mock_logout_api(request: web.Request) -> web.Response:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        engine.session_ochir(token)
    resp = _json({"success": True})
    resp.del_cookie(SESSION_COOKIE)
    return resp


async def mock_me_api(request: web.Request) -> web.Response:
    """Joriy sessiyaga tegishli talaba ma'lumotini qaytaradi (sahifa yangilanganda chaqiriladi)."""
    from database import get_connection, release_connection
    import psycopg2.extras

    talaba_kod = _get_talaba_kod(request)
    if not talaba_kod:
        return _unauthorized()

    conn = get_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT kod, ismlar, sinf, yonalish FROM talabalar WHERE kod=%s",
        (talaba_kod,),
    )
    talaba = cur.fetchone()
    cur.close(); release_connection(conn)
    if not talaba:
        return _unauthorized()
    return _json({"student": dict(talaba)})


# ─────────────────────────────────────────
# Testlar ro'yxati
# ─────────────────────────────────────────

async def mock_tests_api(request: web.Request) -> web.Response:
    talaba_kod = _get_talaba_kod(request)
    if not talaba_kod:
        return _unauthorized()

    exam_key = request.rel_url.query.get("exam_key")
    try:
        tests = engine.talaba_uchun_testlar(exam_key=exam_key)
        return _json({"tests": tests})
    except Exception as e:
        logging.error(f"mock_tests_api error: {e}")
        return _json({"error": "Server xatosi"}, status=500)


async def mock_my_attempts_api(request: web.Request) -> web.Response:
    talaba_kod = _get_talaba_kod(request)
    if not talaba_kod:
        return _unauthorized()
    try:
        attempts = engine.talaba_attemptlari(talaba_kod)
        return _json({"attempts": attempts})
    except Exception as e:
        logging.error(f"mock_my_attempts_api error: {e}")
        return _json({"error": "Server xatosi"}, status=500)


# ─────────────────────────────────────────
# Attempt boshlash / holat
# ─────────────────────────────────────────

async def mock_attempt_start_api(request: web.Request) -> web.Response:
    """POST { test_id } -> attempt_id (mavjud tugallanmagan urinish bo'lsa, o'shani qaytaradi)."""
    talaba_kod = _get_talaba_kod(request)
    if not talaba_kod:
        return _unauthorized()

    try:
        data = await request.json()
        test_id = int(data["test_id"])
        attempt_id = engine.attempt_boshla(talaba_kod, test_id)
        return _json({"attempt_id": attempt_id})
    except Exception as e:
        logging.error(f"mock_attempt_start_api error: {e}")
        return _json({"error": str(e)}, status=500)


async def mock_attempt_status_api(request: web.Request) -> web.Response:
    """GET — attempt umumiy holati: bo'limlar, javob soni, qolgan vaqt."""
    talaba_kod = _get_talaba_kod(request)
    if not talaba_kod:
        return _unauthorized()

    attempt_id = int(request.match_info["id"])
    try:
        status = engine.attempt_umumiy_holat(attempt_id, talaba_kod)
        if not status:
            return _json({"error": "Urinish topilmadi"}, status=404)
        return _json({"attempt": status})
    except Exception as e:
        logging.error(f"mock_attempt_status_api error: {e}")
        return _json({"error": "Server xatosi"}, status=500)


async def mock_section_questions_api(request: web.Request) -> web.Response:
    """GET — bitta bo'limning savollari (to'g'ri javobsiz) yoki Writing matni."""
    talaba_kod = _get_talaba_kod(request)
    if not talaba_kod:
        return _unauthorized()

    attempt_id = int(request.match_info["attempt_id"])
    section_id = int(request.match_info["section_id"])
    try:
        section = engine.section_savollari_talabaga(attempt_id, section_id, talaba_kod)
        if not section:
            return _json({"error": "Topilmadi"}, status=404)
        return _json({"section": section})
    except Exception as e:
        logging.error(f"mock_section_questions_api error: {e}")
        return _json({"error": "Server xatosi"}, status=500)


# ─────────────────────────────────────────
# Javob / insho saqlash
# ─────────────────────────────────────────

async def mock_answer_save_api(request: web.Request) -> web.Response:
    """POST { question_id, answer } -> shu zahoti avtomatik tekshiriladi, lekin natija qaytarilmaydi."""
    talaba_kod = _get_talaba_kod(request)
    if not talaba_kod:
        return _unauthorized()

    attempt_id = int(request.match_info["id"])
    try:
        data = await request.json()
        question_id = int(data["question_id"])
        answer = data.get("answer")
        ok = engine.javob_saqla(attempt_id, question_id, answer, talaba_kod=talaba_kod)
        if not ok and not data.get("allow_blank_save_fail"):
            # ok=False bo'lishi mumkin chunki javob noto'g'ri (normal holat),
            # shuning uchun bu yerda xato deb hisoblamaymiz — faqat saqlanganini tasdiqlaymiz
            pass
        return _json({"success": True})
    except Exception as e:
        logging.error(f"mock_answer_save_api error: {e}")
        return _json({"error": str(e)}, status=500)


async def mock_essay_save_api(request: web.Request) -> web.Response:
    """POST { section_id, text } -> Writing insho matnini saqlaydi (auto-save uchun)."""
    talaba_kod = _get_talaba_kod(request)
    if not talaba_kod:
        return _unauthorized()

    attempt_id = int(request.match_info["id"])
    try:
        data = await request.json()
        section_id = int(data["section_id"])
        text = data.get("text", "")
        engine.essay_saqla(attempt_id, section_id, text, talaba_kod=talaba_kod)
        return _json({"success": True, "word_count": len(text.split())})
    except Exception as e:
        logging.error(f"mock_essay_save_api error: {e}")
        return _json({"error": str(e)}, status=500)


async def mock_attempt_submit_api(request: web.Request) -> web.Response:
    """POST -> mockni yakunlab yuboradi. Natija hali ko'rsatilmaydi."""
    talaba_kod = _get_talaba_kod(request)
    if not talaba_kod:
        return _unauthorized()

    attempt_id = int(request.match_info["id"])
    try:
        ok = engine.attempt_yubor(attempt_id, talaba_kod=talaba_kod)
        return _json({"success": ok})
    except Exception as e:
        logging.error(f"mock_attempt_submit_api error: {e}")
        return _json({"error": str(e)}, status=500)


# ─────────────────────────────────────────
# Statik sahifalar
# ─────────────────────────────────────────

async def mock_login_page(request: web.Request) -> web.Response:
    return web.FileResponse(os.path.join(STATIC_DIR, "mock-login.html"))


async def mock_home_page(request: web.Request) -> web.Response:
    return web.FileResponse(os.path.join(STATIC_DIR, "mock-home.html"))


async def mock_test_page(request: web.Request) -> web.Response:
    return web.FileResponse(os.path.join(STATIC_DIR, "mock-test.html"))


# ─────────────────────────────────────────
# create_app() ichida ro'yxatdan o'tkazish uchun
# ─────────────────────────────────────────

def register_mock_student_routes(app: web.Application) -> None:
    app.middlewares.append(mock_domain_redirect_middleware)

    app.router.add_post("/api/mock/login", mock_login_api)
    app.router.add_post("/api/mock/logout", mock_logout_api)
    app.router.add_get("/api/mock/me", mock_me_api)

    app.router.add_get("/api/mock/tests", mock_tests_api)
    app.router.add_get("/api/mock/my-attempts", mock_my_attempts_api)

    app.router.add_post("/api/mock/attempt/start", mock_attempt_start_api)
    app.router.add_get("/api/mock/attempt/{id}", mock_attempt_status_api)
    app.router.add_get(
        "/api/mock/attempt/{attempt_id}/section/{section_id}",
        mock_section_questions_api,
    )
    app.router.add_post("/api/mock/attempt/{id}/answer", mock_answer_save_api)
    app.router.add_post("/api/mock/attempt/{id}/essay", mock_essay_save_api)
    app.router.add_post("/api/mock/attempt/{id}/submit", mock_attempt_submit_api)

    app.router.add_get("/mock", mock_login_page)
    app.router.add_get("/mock/home", mock_home_page)
    app.router.add_get("/mock/test", mock_test_page)
