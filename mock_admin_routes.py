"""
Mock imtihon — ADMIN API marshrutlari (test/bo'lim/savol boshqarish).

Bu modul `server.py` dagi mavjud naqshlarga (check_admin_role, safe_json_response)
to'liq mos qilib yozilgan. Routes `create_app()` ichida ro'yxatdan o'tkaziladi.
"""

import os
import logging
from aiohttp import web

import mock_exam_engine as engine

STATIC_DIR = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────
# Yordamchi
# ─────────────────────────────────────────

async def _require_admin(request: web.Request):
    """check_admin_role orqali tekshiradi, faqat 'admin' rolini qabul qiladi."""
    from server import check_admin_role
    role, _, error_resp = await check_admin_role(request)
    if error_resp:
        return None, error_resp
    if role != "admin":
        return None, web.json_response(
            {"error": "Faqat adminlar mock imtihonlarni boshqara oladi"}, status=403
        )
    return role, None


async def _get_admin_user_id(request: web.Request) -> int:
    """check_admin_role bilan bir xil naqsh — Telegram user_id'ni qayta olib chiqadi."""
    from server import validate_telegram_init_data
    bot_token = request.app["bot_token"]
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user, _ = validate_telegram_init_data(init_data, bot_token)
    if user:
        return user.get("id", 0)
    try:
        return int(request.rel_url.query.get("user_id", 0))
    except ValueError:
        return 0


# ─────────────────────────────────────────
# Imtihon turlari (dropdown uchun: IELTS, CEFR, ...)
# ─────────────────────────────────────────

async def admin_mock_exam_types_api(request: web.Request) -> web.Response:
    _, error_resp = await _require_admin(request)
    if error_resp:
        return error_resp

    from mock_database import exam_types_ol
    try:
        types = exam_types_ol(faqat_aktiv=False)
        return web.json_response({"exam_types": types})
    except Exception as e:
        logging.error(f"admin_mock_exam_types_api error: {e}")
        return web.json_response({"error": "Server xatosi"}, status=500)


# ─────────────────────────────────────────
# Testlar (mock_tests)
# ─────────────────────────────────────────

async def admin_mock_tests_api(request: web.Request) -> web.Response:
    """GET: ro'yxat | POST: yangi test yaratish"""
    _, error_resp = await _require_admin(request)
    if error_resp:
        return error_resp

    method = request.method
    try:
        if method == "GET":
            exam_key = request.rel_url.query.get("exam_key")
            tests = engine.testlar_royhati(exam_key=exam_key, faqat_aktiv=False)
            return web.json_response({"tests": tests})

        elif method == "POST":
            data = await request.json()
            exam_key = data.get("exam_key", "").strip()
            title = data.get("title", "").strip()
            duration_minutes = int(data.get("duration_minutes", 60))

            if not exam_key or not title:
                return web.json_response(
                    {"error": "exam_key va title majburiy"}, status=400
                )

            test_id = engine.test_yarat(exam_key, title, duration_minutes)
            return web.json_response({"success": True, "id": test_id})

    except Exception as e:
        logging.error(f"admin_mock_tests_api error: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def admin_mock_test_detail_api(request: web.Request) -> web.Response:
    """GET: bitta testni bo'limlari bilan | PUT: faollik/sozlama | DELETE: o'chirish"""
    _, error_resp = await _require_admin(request)
    if error_resp:
        return error_resp

    test_id = int(request.match_info["id"])
    method = request.method
    try:
        if method == "GET":
            test = engine.test_ol(test_id)
            if not test:
                return web.json_response({"error": "Test topilmadi"}, status=404)
            return web.json_response({"test": test})

        elif method == "PUT":
            data = await request.json()
            if "is_active" in data:
                engine.test_faollik(test_id, bool(data["is_active"]))
            return web.json_response({"success": True})

        elif method == "DELETE":
            ok = engine.test_ochir(test_id)
            return web.json_response({"success": ok})

    except Exception as e:
        logging.error(f"admin_mock_test_detail_api error: {e}")
        return web.json_response({"error": str(e)}, status=500)


# ─────────────────────────────────────────
# Bo'limlar (mock_test_sections)
# ─────────────────────────────────────────

async def admin_mock_sections_api(request: web.Request) -> web.Response:
    """POST: bo'lim qo'shish/yangilash (test_id + section_key bo'yicha upsert)"""
    _, error_resp = await _require_admin(request)
    if error_resp:
        return error_resp

    try:
        data = await request.json()
        test_id = int(data["test_id"])
        section_key = data["section_key"].strip()       # listening / reading / writing
        label = data.get("label", "").strip() or section_key.capitalize()
        audio_url = data.get("audio_url") or None
        instructions = data.get("instructions") or None
        sort_order = int(data.get("sort_order", 0))

        section_id = engine.section_qosh(
            test_id, section_key, label, audio_url, instructions, sort_order
        )
        return web.json_response({"success": True, "id": section_id})

    except KeyError as e:
        return web.json_response({"error": f"Maydon yetishmaydi: {e}"}, status=400)
    except Exception as e:
        logging.error(f"admin_mock_sections_api error: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def admin_mock_section_detail_api(request: web.Request) -> web.Response:
    """GET: bo'lim + savollari"""
    _, error_resp = await _require_admin(request)
    if error_resp:
        return error_resp

    section_id = int(request.match_info["id"])
    try:
        section = engine.section_ol(section_id)
        if not section:
            return web.json_response({"error": "Bo'lim topilmadi"}, status=404)
        section["questions"] = engine.savollar_ol(section_id, include_answers=True)
        return web.json_response({"section": section})
    except Exception as e:
        logging.error(f"admin_mock_section_detail_api error: {e}")
        return web.json_response({"error": str(e)}, status=500)


# ─────────────────────────────────────────
# Savollar (mock_test_questions)
# ─────────────────────────────────────────

async def admin_mock_questions_api(request: web.Request) -> web.Response:
    """POST: yangi savol qo'shish"""
    _, error_resp = await _require_admin(request)
    if error_resp:
        return error_resp

    try:
        data = await request.json()
        section_id = int(data["section_id"])
        question_type = data["question_type"].strip()   # mcq/true_false/fill_blank/matching
        question_text = data["question_text"].strip()
        content = data.get("content", {})
        correct_answer = data.get("correct_answer", {})
        points = float(data.get("points", 1))
        sort_order = int(data.get("sort_order", 0))

        if question_type not in ("mcq", "true_false", "fill_blank", "matching"):
            return web.json_response({"error": "Noma'lum savol turi"}, status=400)

        q_id = engine.savol_qosh(
            section_id, question_type, question_text,
            content, correct_answer, points, sort_order,
        )
        return web.json_response({"success": True, "id": q_id})

    except KeyError as e:
        return web.json_response({"error": f"Maydon yetishmaydi: {e}"}, status=400)
    except Exception as e:
        logging.error(f"admin_mock_questions_api error: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def admin_mock_question_detail_api(request: web.Request) -> web.Response:
    """PUT: savolni tahrirlash | DELETE: o'chirish"""
    _, error_resp = await _require_admin(request)
    if error_resp:
        return error_resp

    question_id = int(request.match_info["id"])
    method = request.method
    try:
        if method == "PUT":
            data = await request.json()
            ok = engine.savol_yangila(
                question_id,
                question_text=data.get("question_text"),
                content=data.get("content"),
                correct_answer=data.get("correct_answer"),
                points=data.get("points"),
                sort_order=data.get("sort_order"),
            )
            return web.json_response({"success": ok})

        elif method == "DELETE":
            ok = engine.savol_ochir(question_id)
            return web.json_response({"success": ok})

    except Exception as e:
        logging.error(f"admin_mock_question_detail_api error: {e}")
        return web.json_response({"error": str(e)}, status=500)


# ─────────────────────────────────────────
# Tekshirish navbati (keyingi bosqichda to'liq ishlatiladi)
# ─────────────────────────────────────────

async def admin_mock_pending_api(request: web.Request) -> web.Response:
    """Tekshirilmagan (submitted) urinishlar ro'yxati."""
    _, error_resp = await _require_admin(request)
    if error_resp:
        return error_resp

    try:
        pending = engine.tekshirish_kutayotganlar()
        return web.json_response({"pending": pending})
    except Exception as e:
        logging.error(f"admin_mock_pending_api error: {e}")
        return web.json_response({"error": "Server xatosi"}, status=500)


async def admin_mock_attempt_detail_api(request: web.Request) -> web.Response:
    """Bitta urinishning to'liq tafsiloti (javoblar + insholar)."""
    _, error_resp = await _require_admin(request)
    if error_resp:
        return error_resp

    attempt_id = int(request.match_info["id"])
    try:
        detail = engine.attempt_tafsilot(attempt_id)
        if not detail:
            return web.json_response({"error": "Urinish topilmadi"}, status=404)
        return web.json_response({"attempt": detail})
    except Exception as e:
        logging.error(f"admin_mock_attempt_detail_api error: {e}")
        return web.json_response({"error": "Server xatosi"}, status=500)


async def admin_mock_attempt_finalize_api(request: web.Request) -> web.Response:
    """
    POST { sections: {listening: 7.0, reading: 6.5, writing: 6.0, speaking: 7.0},
           level_label: 'B2' (CEFR uchun), notes: '...' }

    Adminning yakuniy ballarini mavjud `mock_database.mock_natija_qosh()` orqali
    `mock_natijalari`ga yozadi va shu attempt'ni 'released' holatga o'tkazib,
    natija id'sini bog'laydi — talaba shu zahoti odatdagi natija sahifasida ko'radi.
    """
    _, error_resp = await _require_admin(request)
    if error_resp:
        return error_resp

    attempt_id = int(request.match_info["id"])
    try:
        data = await request.json()
        sections = data.get("sections") or {}
        level_label = data.get("level_label") or None
        notes = data.get("notes") or None

        if not sections:
            return web.json_response({"error": "Kamida bitta bo'lim balli kiritilishi kerak"}, status=400)

        meta = engine.attempt_meta(attempt_id)
        if not meta:
            return web.json_response({"error": "Urinish topilmadi"}, status=404)
        if meta["status"] not in ("submitted", "reviewed"):
            return web.json_response(
                {"error": "Bu urinish hali yuborilmagan yoki allaqachon yakunlangan"}, status=400
            )

        admin_id = await _get_admin_user_id(request)

        from mock_database import mock_natija_qosh
        natija_id = mock_natija_qosh(
            talaba_kod=meta["talaba_kod"],
            exam_key=meta["exam_key"],
            sections=sections,
            level_label=level_label,
            notes=notes,
            admin_id=admin_id,
        )
        engine.attempt_natija_biriktir(attempt_id, natija_id, admin_id)

        return web.json_response({"success": True, "natija_id": natija_id})

    except Exception as e:
        logging.error(f"admin_mock_attempt_finalize_api error: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def mock_admin_page_handler(request: web.Request) -> web.Response:
    """Admin uchun mock savol qo'shish sahifasi (mock-admin.html)."""
    html_path = os.path.join(STATIC_DIR, "mock-admin.html")
    return web.FileResponse(html_path)


async def mock_review_page_handler(request: web.Request) -> web.Response:
    """Admin uchun tekshirish/baholash sahifasi (mock-review.html)."""
    html_path = os.path.join(STATIC_DIR, "mock-review.html")
    return web.FileResponse(html_path)


# ─────────────────────────────────────────
# create_app() ichida ro'yxatdan o'tkazish uchun
# ─────────────────────────────────────────

def register_mock_admin_routes(app: web.Application) -> None:
    app.router.add_get("/api/admin/mock/exam-types", admin_mock_exam_types_api)

    app.router.add_get("/api/admin/mock/tests", admin_mock_tests_api)
    app.router.add_post("/api/admin/mock/tests", admin_mock_tests_api)
    app.router.add_get("/api/admin/mock/tests/{id}", admin_mock_test_detail_api)
    app.router.add_put("/api/admin/mock/tests/{id}", admin_mock_test_detail_api)
    app.router.add_delete("/api/admin/mock/tests/{id}", admin_mock_test_detail_api)

    app.router.add_post("/api/admin/mock/sections", admin_mock_sections_api)
    app.router.add_get("/api/admin/mock/sections/{id}", admin_mock_section_detail_api)

    app.router.add_post("/api/admin/mock/questions", admin_mock_questions_api)
    app.router.add_put("/api/admin/mock/questions/{id}", admin_mock_question_detail_api)
    app.router.add_delete("/api/admin/mock/questions/{id}", admin_mock_question_detail_api)

    app.router.add_get("/api/admin/mock/pending", admin_mock_pending_api)
    app.router.add_get("/api/admin/mock/attempt/{id}", admin_mock_attempt_detail_api)
    app.router.add_post("/api/admin/mock/attempt/{id}/finalize", admin_mock_attempt_finalize_api)

    app.router.add_get("/mock-admin", mock_admin_page_handler)
    app.router.add_get("/mock-review", mock_review_page_handler)
