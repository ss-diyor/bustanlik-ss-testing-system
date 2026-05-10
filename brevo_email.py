def build_announcement_html(title: str, body: str, recipient_name: str = "", sender_name: str = None) -> str:
    _, _, cfg_sender = _get_config()
    sender = sender_name or cfg_sender or "Maktab Administratsiyasi"
    greeting = (
        f"Hurmatli {recipient_name.strip()},"
        if recipient_name and recipient_name.strip()
        else "Assalomu alaykum,"
    )
    body_html = body.replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{ margin:0; padding:0; background:#f0f4f8; font-family:Arial,Helvetica,sans-serif; }}
    .wrap {{ width:100%; background:#f0f4f8; padding:20px 0; }}
    .card {{ background:#fff; border-radius:12px; overflow:hidden; max-width:560px;
             margin:0 auto; box-shadow:0 4px 16px rgba(0,0,0,.10); }}
    .logo-cell {{ text-align:center; padding:24px 24px 12px; background:#fff; }}
    .logo-cell img {{ width:140px; max-width:60%; height:auto; display:block; margin:0 auto; }}
    .divider {{ border:none; border-top:1px solid #e2e8f0; margin:0 24px; }}
    .header {{ background:#1a3a8f; padding:20px 24px; }}
    .header .label {{ margin:0 0 4px; font-size:11px; color:#a0b4e8; letter-spacing:1px; }}
    .header h1 {{ margin:0; font-size:20px; color:#fff; line-height:1.35; font-weight:700; }}
    .body-cell {{ padding:24px 24px 8px; }}
    .body-cell .greet {{ margin:0 0 12px; font-size:15px; color:#374151; font-weight:600; }}
    .body-cell .text  {{ margin:0; font-size:15px; color:#374151; line-height:1.75; }}
    .btn-cell {{ padding:20px 24px 24px; }}
    .btn {{ display:inline-block; background:#1a3a8f; color:#fff !important;
            font-size:13px; font-weight:600; text-decoration:none;
            padding:10px 18px; border-radius:8px; margin:4px 6px 4px 0; }}
    .footer {{ background:#f8fafc; padding:16px 24px; border-top:1px solid #e2e8f0; }}
    .footer p {{ margin:0 0 4px; font-size:12px; color:#6b7280; }}
    .footer a {{ color:#1a3a8f; text-decoration:none; }}
    .copy {{ margin:14px 0 0; font-size:11px; color:#9ca3af; text-align:center; }}
    @media (max-width:600px) {{
      .card {{ border-radius:0 !important; }}
      .header h1 {{ font-size:17px; }}
      .body-cell .text {{ font-size:14px; }}
      .btn {{ display:block; text-align:center; margin:6px 0; }}
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

    <!-- Header -->
    <div class="header">
      <p class="label">📢 E'LON</p>
      <h1>{title}</h1>
    </div>

    <!-- Matn -->
    <div class="body-cell">
      <p class="greet">{greeting}</p>
      <p class="text">{body_html}</p>
    </div>

    <!-- Tugmalar -->
    <div class="btn-cell">
      <a class="btn" href="{TELEGRAM_BOT_URL}" target="_blank">🤖 Botga o'tish</a>
      <a class="btn" href="{TELEGRAM_KANAL_URL}" target="_blank">📢 Kanalga o'tish</a>
    </div>

    <!-- Footer -->
    <div class="footer">
      <p>Bu xabar <strong style="color:#1a3a8f;">{sender}</strong> tomonidan yuborildi.</p>
      <p>Savollar: <a href="{TELEGRAM_BOT_URL}">@BustanlikSStestingsystembot</a></p>
    </div>

  </div>
  <p class="copy">© 2026 Bo'stonliq tuman ixtisoslashtirilgan maktabi.</p>
</div>
</body>
</html>"""
