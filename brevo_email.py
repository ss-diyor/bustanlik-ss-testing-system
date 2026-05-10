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
import aiohttp

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def _get_config():
    from config import BREVO_API_KEY, BREVO_SENDER_EMAIL, BREVO_SENDER_NAME
    return BREVO_API_KEY, BREVO_SENDER_EMAIL, BREVO_SENDER_NAME


async def send_email(to_email: str, to_name: str, subject: str, html_content: str) -> bool:
    """
    Bitta email yuboradi.

    Qaytaradi:
        True  — muvaffaqiyatli
        False — xato
    """
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
    html_content: str,
) -> tuple[int, int]:
    """
    Ko'p emailga yuboradi.

    recipients — [{"email": "...", "name": "..."}, ...] ro'yxat

    Qaytaradi: (muvaffaqiyatli_soni, xato_soni)
    """
    ok = 0
    fail = 0
    for r in recipients:
        success = await send_email(
            to_email=r["email"],
            to_name=r.get("name", ""),
            subject=subject,
            html_content=html_content,
        )
        if success:
            ok += 1
        else:
            fail += 1
    return ok, fail


def build_announcement_html(title: str, body: str, sender_name: str) -> str:
    """
    Yangilik emaili uchun oddiy HTML shablon.
    """
    body_html = body.replace("\n", "<br>")
    return f"""
<!DOCTYPE html>
<html lang="uz">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f9;padding:30px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:8px;overflow:hidden;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <!-- Header -->
        <tr>
          <td style="background:#1a73e8;padding:28px 32px;">
            <p style="margin:0;font-size:13px;color:#c8daff;">📢 E'LON</p>
            <h1 style="margin:8px 0 0;font-size:22px;color:#ffffff;line-height:1.3;">
              {title}
            </h1>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:32px;">
            <p style="margin:0;font-size:15px;color:#333333;line-height:1.7;">
              {body_html}
            </p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#f8f9fa;padding:16px 32px;border-top:1px solid #e8eaed;">
            <p style="margin:0;font-size:12px;color:#888888;">
              Bu xabar <strong>{sender_name}</strong> tomonidan yuborildi.<br>
              Savollar bo'lsa, maktab administratsiyasiga murojaat qiling.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""
