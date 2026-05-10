"""
Brevo (Sendinblue) orqali email yuborish moduli.

Foydalanish:
    from brevo_email import send_email, send_bulk_emails

Environment variables (.env yoki Railway Variables):
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


async def send_bulk_emails(recipients: list[dict], subject: str, html_content: str) -> tuple[int, int]:
    ok = fail = 0
    for i, r in enumerate(recipients):
        if i > 0 and i % 50 == 0:
            await asyncio.sleep(1.0)
        html = build_announcement_html(
            title=subject,
            body=html_content,
            recipient_name=r.get("name", ""),
        )
        success = await send_email(r["email"], r.get("name", ""), subject, html)
        if success:
            ok += 1
        else:
            fail += 1
    return ok, fail


def build_announcement_html(title: str, body: str, recipient_name: str = "", sender_name: str = None) -> str:
    _, _, sender_name = _get_config()
    greeting = f"Hurmatli {recipient_name.strip()}," if recipient_name and recipient_name.strip() else "Assalomu alaykum,"
    body_html = body.replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f0f4f8;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0f4f8;padding:30px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0"
           style="background:#ffffff;border-radius:12px;overflow:hidden;
                  box-shadow:0 4px 16px rgba(0,0,0,0.10);max-width:600px;width:100%;">

      <!-- LOGO -->
      <tr>
        <td align="center" style="background:#ffffff;padding:28px 32px 16px;">
          <img src="{MAKTAB_LOGO_URL}" alt="Bo'stonliq maktabi"
               width="160" style="display:block;max-width:160px;height:auto;border:0;">
        </td>
      </tr>

      <!-- Ajratuvchi -->
      <tr><td style="padding:0 32px;">
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:0;">
      </td></tr>

      <!-- Header -->
      <tr>
        <td style="background:#1a3a8f;padding:24px 32px;">
          <p style="margin:0 0 6px;font-size:12px;color:#a0b4e8;letter-spacing:1px;">📢 E'LON</p>
          <h1 style="margin:0;font-size:22px;color:#ffffff;line-height:1.35;font-weight:700;">{title}</h1>
        </td>
      </tr>

      <!-- Matn -->
      <tr>
        <td style="padding:28px 32px 8px;">
          <p style="margin:0 0 16px;font-size:15px;color:#374151;font-weight:600;">{greeting}</p>
          <p style="margin:0;font-size:15px;color:#374151;line-height:1.75;">{body_html}</p>
        </td>
      </tr>

      <!-- Telegram tugmalari -->
      <tr>
        <td style="padding:24px 32px 28px;">
          <table cellpadding="0" cellspacing="0"><tr>
            <td style="padding-right:10px;">
              <a href="{TELEGRAM_BOT_URL}" target="_blank"
                 style="display:inline-block;background:#1a3a8f;color:#ffffff;
                        font-size:13px;font-weight:600;text-decoration:none;
                        padding:10px 20px;border-radius:8px;">
                🤖 Botga o'tish
              </a>
            </td>
            <td>
              <a href="{TELEGRAM_KANAL_URL}" target="_blank"
                 style="display:inline-block;background:#1a3a8f;color:#ffffff;
                        font-size:13px;font-weight:600;text-decoration:none;
                        padding:10px 20px;border-radius:8px;">
                📢 Kanalga o'tish
              </a>
            </td>
          </tr></table>
        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="background:#f8fafc;padding:20px 32px;border-top:1px solid #e2e8f0;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td>
              <p style="margin:0 0 6px;font-size:12px;color:#6b7280;">
                Bu xabar <strong style="color:#1a3a8f;">{sender_name}</strong> tomonidan yuborildi.
              </p>
              <p style="margin:0;font-size:12px;color:#9ca3af;">
                Savollar uchun:
                <a href="{TELEGRAM_BOT_URL}" style="color:#1a3a8f;text-decoration:none;">
                  @BustanlikSStestingsystembot
                </a>
              </p>
            </td>
            <td align="right" style="vertical-align:middle;">
              <a href="{TELEGRAM_KANAL_URL}" target="_blank" style="text-decoration:none;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Telegram_logo.svg/64px-Telegram_logo.svg.png"
                     width="28" height="28" alt="Telegram" style="display:block;border:0;">
              </a>
            </td>
          </tr></table>
        </td>
      </tr>

    </table>
    <p style="margin:16px 0 0;font-size:11px;color:#9ca3af;text-align:center;">
      © 2026 Bo'stonliq tuman ixtisoslashtirilgan maktabi.
    </p>
  </td></tr>
</table>
</body>
</html>"""
