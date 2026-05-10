"""
Brevo (Sendinblue) orqali email yuborish moduli.

Environment variables (Railway Variables):
    BREVO_API_KEY      — Brevo API kaliti (majburiy)
    BREVO_SENDER_EMAIL — Jo'natuvchi email (masalan: noreply@maktab.uz)
    BREVO_SENDER_NAME  — Jo'natuvchi ismi (masalan: Bo'stonliq SS Maktab)
"""

import logging
import asyncio
import aiohttp

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

MAKTAB_LOGO_URL = (
    "https://raw.githubusercontent.com/ss-diyor/"
    "bustanlik-ss-testing-system/main/logo.png"
)
TELEGRAM_BOT_URL   = "https://t.me/BustanlikSStestingsystembot"
TELEGRAM_KANAL_URL = "https://t.me/Bustanlikspecializedschool"


def _get_config():
    from config import BREVO_API_KEY, BREVO_SENDER_EMAIL, BREVO_SENDER_NAME
    return BREVO_API_KEY, BREVO_SENDER_EMAIL, BREVO_SENDER_NAME


async def send_email(to_email: str, to_name: str, subject: str, html_content: str) -> bool:
    api_key, sender_email, sender_name = _get_config()
    if not api_key:
        logger.warning("BREVO_API_KEY sozlanmagan — email yuborilmadi.")
        return False
    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_content,
    }
    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(BREVO_API_URL, json=payload, headers=headers) as resp:
                if resp.status in (200, 201):
                    logger.info(f"Email yuborildi: {to_email}")
                    return True
                else:
                    body = await resp.text()
                    logger.error(f"Brevo xato {resp.status}: {body}")
                    return False
    except Exception as e:
        logger.error(f"Email yuborishda istisno: {e}")
        return False


async def send_bulk_emails(
    recipients: list[dict],
    subject: str,
    body: str,
) -> tuple[int, int]:
    """
    Har bir recipient uchun HTML alohida quriladi —
    shu tarzda "Hurmatli [Ism]," personalizatsiyasi ishlaydi.

    recipients: [{"name": "Jasur Toshmatov", "email": "jasur@gmail.com"}, ...]
    subject:    Email mavzusi
    body:       Xabar matni (oddiy matn, HTML emas)
    """
    ok = fail = 0
    for i, r in enumerate(recipients):
        if i > 0 and i % 50 == 0:
            await asyncio.sleep(1.0)

        # Har bir o'quvchi / ota-ona uchun alohida HTML
        html = build_announcement_html(
            title=subject,
            body=body,
            recipient_name=r.get("name", ""),
        )
        success = await send_email(r["email"], r.get("name", ""), subject, html)
        if success:
            ok += 1
        else:
            fail += 1
    return ok, fail


def build_announcement_html(title: str, body: str, recipient_name: str = "") -> str:
    """
    Chiroyli HTML email shabloni.
    recipient_name berilsa → "Hurmatli Jasur Toshmatov,"
    berilmasa           → "Assalomu alaykum,"
    """
    name = recipient_name.strip()
    if name:
        # Faqat ismni olish (masalan "Jasur Toshmatov ota-onasi" → "Jasur Toshmatov ota-onasi")
        greeting = f"Hurmatli {name},"
    else:
        greeting = "Assalomu alaykum,"

    body_html = body.replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{ margin:0; padding:0; background:#f0f4f8; font-family:Arial,Helvetica,sans-serif; }}
    .wrap {{ width:100%; background:#f0f4f8; padding:24px 0; box-sizing:border-box; }}
    .card {{ background:#fff; border-radius:12px; overflow:hidden; max-width:540px;
             margin:0 auto; box-shadow:0 4px 20px rgba(0,0,0,.10); width:92%; }}
    .logo-cell {{ text-align:center; padding:28px 24px 16px; }}
    .logo-cell img {{ width:130px; max-width:55%; height:auto; display:block; margin:0 auto; }}
    .divider {{ border:none; border-top:1px solid #e2e8f0; margin:0; }}
    .header {{ background:#1a3a8f; padding:22px 28px; }}
    .header .label {{ margin:0 0 6px; font-size:11px; color:#a0b4e8; letter-spacing:1.5px; }}
    .header h1 {{ margin:0; font-size:20px; color:#fff; line-height:1.4; font-weight:700; }}
    .content {{ padding:28px 28px 12px; }}
    .greet {{ margin:0 0 14px; font-size:15px; color:#1a3a8f; font-weight:700; }}
    .text {{ margin:0; font-size:15px; color:#374151; line-height:1.8; }}
    .btn-wrap {{ padding:22px 28px 28px; }}
    .btn {{ display:inline-block; background:#1a3a8f; color:#fff !important;
            font-size:13px; font-weight:600; text-decoration:none;
            padding:11px 22px; border-radius:8px; margin:0 8px 8px 0; }}
    .footer {{ background:#f1f5f9; padding:18px 28px; border-top:1px solid #e2e8f0; text-align:center; }}
    .footer p {{ margin:0 0 4px; font-size:12px; color:#6b7280; }}
    .footer a {{ color:#1a3a8f; text-decoration:none; font-weight:600; }}
    .copy {{ margin:16px 0 0; font-size:11px; color:#9ca3af; text-align:center; }}
    @media (max-width:600px) {{
      .card {{ width:96%; border-radius:8px; }}
      .header {{ padding:18px 20px; }}
      .header h1 {{ font-size:17px; }}
      .content {{ padding:22px 20px 8px; }}
      .btn-wrap {{ padding:16px 20px 22px; }}
      .btn {{ display:block; text-align:center; margin:0 0 10px 0; }}
      .footer {{ padding:16px 20px; }}
    }}
  </style>
</head>
<body>
<div class="wrap">
  <div class="card">

    <!-- Logo -->
    <div class="logo-cell">
      <img src="{MAKTAB_LOGO_URL}" alt="Bo'stonliq maktabi">
    </div>
    <hr class="divider">

    <!-- Sarlavha -->
    <div class="header">
      <p class="label">📢 E'LON</p>
      <h1>{title}</h1>
    </div>

    <!-- Matn -->
    <div class="content">
      <p class="greet">{greeting}</p>
      <p class="text">{body_html}</p>
    </div>

    <!-- Tugmalar -->
    <div class="btn-wrap">
      <a class="btn" href="{TELEGRAM_BOT_URL}" target="_blank">🤖 Botga o'tish</a>
      <a class="btn" href="{TELEGRAM_KANAL_URL}" target="_blank">📢 Kanalga o'tish</a>
    </div>

    <!-- Footer -->
    <div class="footer">
      <p><a href="{TELEGRAM_KANAL_URL}">Bo'stonliq tuman ixtisoslashtirilgan maktabi</a></p>
      <p>© 2026 Barcha huquqlar himoyalangan.</p>
    </div>

  </div>
  <p class="copy">Bu xabar avtomatik tarzda yuborildi.</p>
</div>
</body>
</html>"""
