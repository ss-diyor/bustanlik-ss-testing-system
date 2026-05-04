"""
Sertifikat generatori.
Barcha matn, rang va logo sozlamalari database'dan o'qiladi.
Admin panelidan o'zgartirish mumkin (cert_admin.py).

Dizayn rejimlari:
  • "colored_border"  — rangli ramkali (avvalgi ko'rinish)
  • "national_bg"     — milliy naqshli orqa fon (national_background.png)
"""
from __future__ import annotations

import hashlib
import io
import os
from fpdf import FPDF

# ── Default sozlamalar ────────────────────────────────────────────────────────
CERT_DEFAULTS: dict[str, str] = {
    "cert_sarlavha":    "SERTIFIKAT",
    "cert_subtitle":    "O'quvchining ismi va familyasi",
    "cert_maktab_nomi": "Bo'stonliq tumani ixtisoslashtirilgan maktabining",
    "cert_matn":        "Bustanlik SS Testing System DTM imtihonida olingan ball",
    "cert_rang_r":      "0",
    "cert_rang_g":      "0",
    "cert_rang_b":      "128",
    "cert_logo_path":   "",
    # Yangi: dizayn rejimi
    "cert_dizayn":      "colored_border",   # "colored_border" | "national_bg"
    "cert_bg_path":     "national_background.png",
}


def generate_cert_hash(kod: str, ism: str, ball, sana: str) -> str:
    """
    Sertifikat uchun unikal SHA-256 hash generatsiya qiladi.
    Bu hash blockchain-ga asoslangan tekshiruv uchun ishlatiladi —
    sertifikat ma'lumotlari o'zgartirilsa, hash mos kelmaydi.

    Parametrlar:
        kod  — o'quvchining unikal kodi
        ism  — to'liq ismi
        ball — olingan ball
        sana — sertifikat sanasi (string)
    """
    try:
        from config import BOT_TOKEN  # maxfiy tuz sifatida
        salt = BOT_TOKEN
    except Exception:
        salt = "bustanlik-ss"  # fallback

    raw = f"{kod}|{ism}|{ball}|{sana}|{salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _to_int(val: str, fallback: int) -> int:
    try:
        return max(0, min(255, int(val)))
    except (ValueError, TypeError):
        return fallback


class CertificateGenerator:
    """
    Sertifikat generatori.

    Oddiy ishlatilish:
        gen = CertificateGenerator()           # default sozlamalar
        gen = CertificateGenerator(settings)   # dict bilan
        gen = CertificateGenerator.from_db()   # database'dan (tavsiya etiladi)
    """

    def __init__(self, settings: dict[str, str] | None = None):
        self.output_dir = "certificates"
        os.makedirs(self.output_dir, exist_ok=True)
        merged = dict(CERT_DEFAULTS)
        if settings:
            merged.update(settings)
        self._s = merged
        self.unicode_font_family = "DejaVuSans"
        self.unicode_font_ready = False

    @classmethod
    def from_db(cls) -> "CertificateGenerator":
        try:
            from database import get_setting
            settings = {k: get_setting(k, v) for k, v in CERT_DEFAULTS.items()}
        except Exception:
            settings = {}
        return cls(settings)

    # ── Asosiy metod ──────────────────────────────────────────────────────────

    def generate(self, full_name, score, date, kod, sinf="", maktab="") -> tuple[str, str]:
        """
        Sertifikat PDF faylini generatsiya qiladi.
        Returns: (pdf_path, cert_hash) — fayl yo'li va SHA-256 hash
        """
        cert_hash = generate_cert_hash(kod, full_name, score, str(date))
        dizayn = self._s.get("cert_dizayn", "colored_border").strip()
        if dizayn == "national_bg":
            pdf_path = self._generate_national_bg(full_name, score, date, kod)
        else:
            pdf_path = self._generate_colored_border(full_name, score, date, kod)
        return pdf_path, cert_hash

    # ── 1-DIZAYN: Rangli ramkali (avvalgi ko'rinish) ──────────────────────────

    def _generate_colored_border(self, full_name, score, date, kod) -> str:
        s = self._s
        r = _to_int(s["cert_rang_r"], 0)
        g = _to_int(s["cert_rang_g"], 0)
        b = _to_int(s["cert_rang_b"], 128)

        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=False)
        pdf.add_page()
        self.unicode_font_ready = self._configure_unicode_fonts(pdf)

        name_to_print = str(full_name or "")
        if not self.unicode_font_ready:
            name_to_print = self._to_latin1_safe(name_to_print)

        PAGE_W, PAGE_H = 297, 210

        logo_path = s.get("cert_logo_path", "").strip()
        has_logo  = bool(logo_path and os.path.exists(logo_path))
        logo_h_mm = 40 if has_logo else 0
        logo_gap  = 6  if has_logo else 0

        h_sarlavha, h_subtitle, h_name = 18, 8, 20
        h_maktab, h_matn, h_ball = 8, 7, 15

        CONTENT_H = logo_h_mm + logo_gap + h_sarlavha + h_subtitle + h_name + h_maktab + h_matn + h_ball
        y_cursor  = 14 + max(0, (PAGE_H - 14 - 12 - CONTENT_H) * 0.35)

        # Chegara
        pdf.set_draw_color(r, g, b)
        pdf.set_line_width(3)
        pdf.rect(8, 8, 281, 194)
        pdf.set_line_width(0.8)
        pdf.rect(11, 11, 275, 188)

        # Logo
        if has_logo:
            try:
                lw = 40
                pdf.image(logo_path, x=(PAGE_W - lw) / 2, y=y_cursor, w=lw, h=logo_h_mm)
                y_cursor += logo_h_mm + logo_gap
            except Exception:
                pass

        # Sarlavha
        pdf.set_y(y_cursor)
        pdf.set_text_color(r, g, b)
        self._set_font(pdf, "B", 42)
        pdf.cell(0, h_sarlavha, self._safe(s["cert_sarlavha"]), ln=True, align="C")
        pdf.set_text_color(0, 0, 0)
        y_cursor += h_sarlavha

        pdf.set_y(y_cursor)
        self._set_font(pdf, "", 18)
        pdf.cell(0, h_subtitle, self._safe(s["cert_subtitle"]), ln=True, align="C")
        y_cursor += h_subtitle

        pdf.set_y(y_cursor)
        self._set_font(pdf, "B", 34)
        pdf.cell(0, h_name, name_to_print, ln=True, align="C")
        y_cursor += h_name

        pdf.set_y(y_cursor)
        self._set_font(pdf, "", 14)
        pdf.cell(0, h_maktab, self._safe(s["cert_maktab_nomi"]), ln=True, align="C")
        y_cursor += h_maktab

        pdf.set_y(y_cursor)
        pdf.cell(0, h_matn, self._safe(s["cert_matn"]), ln=True, align="C")
        y_cursor += h_matn

        pdf.set_y(y_cursor)
        self._set_font(pdf, "B", 28)
        pdf.set_text_color(r, g, b)
        pdf.cell(0, h_ball, f"{score} BALL", ln=True, align="C")
        pdf.set_text_color(0, 0, 0)

        # Footer
        self._set_font(pdf, "I", 11)
        pdf.set_xy(20, 183)
        pdf.cell(100, 6, f"Sana: {date}", ln=0, align="L")
        pdf.set_xy(20, 189)
        pdf.cell(100, 6, f"Shaxsiy kod: {kod}", ln=0, align="L")

        self._add_qr(pdf, kod, PAGE_W, PAGE_H)

        out = os.path.join(self.output_dir, f"cert_{kod}.pdf")
        pdf.output(out)
        return out

    # ── 2-DIZAYN: Milliy naqshli orqa fon ────────────────────────────────────

    def _generate_national_bg(self, full_name, score, date, kod) -> str:
        s = self._s
        r = _to_int(s["cert_rang_r"], 0)
        g = _to_int(s["cert_rang_g"], 0)
        b = _to_int(s["cert_rang_b"], 128)

        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=False)
        pdf.add_page()
        self.unicode_font_ready = self._configure_unicode_fonts(pdf)

        name_to_print = str(full_name or "")
        if not self.unicode_font_ready:
            name_to_print = self._to_latin1_safe(name_to_print)

        PAGE_W, PAGE_H = 297, 210

        # Orqa fon rasmini to'liq sahifaga qo'yish
        bg_path = s.get("cert_bg_path", "national_background.png").strip()
        if bg_path and os.path.exists(bg_path):
            try:
                pdf.image(bg_path, x=0, y=0, w=PAGE_W, h=PAGE_H)
            except Exception:
                pass

        logo_path = s.get("cert_logo_path", "").strip()
        has_logo  = bool(logo_path and os.path.exists(logo_path))
        logo_h_mm = 35 if has_logo else 0
        logo_gap  = 5  if has_logo else 0

        h_sarlavha, h_subtitle, h_name = 18, 8, 20
        h_maktab, h_matn, h_ball = 8, 7, 15

        CONTENT_H = logo_h_mm + logo_gap + h_sarlavha + h_subtitle + h_name + h_maktab + h_matn + h_ball
        y_cursor  = 18 + max(0, (PAGE_H - 18 - 12 - CONTENT_H) * 0.35)

        # Logo
        if has_logo:
            try:
                lw = 35
                pdf.image(logo_path, x=(PAGE_W - lw) / 2, y=y_cursor, w=lw, h=logo_h_mm)
                y_cursor += logo_h_mm + logo_gap
            except Exception:
                pass

        # Sarlavha
        pdf.set_y(y_cursor)
        pdf.set_text_color(r, g, b)
        self._set_font(pdf, "B", 42)
        pdf.cell(0, h_sarlavha, self._safe(s["cert_sarlavha"]), ln=True, align="C")
        pdf.set_text_color(0, 0, 0)
        y_cursor += h_sarlavha

        pdf.set_y(y_cursor)
        self._set_font(pdf, "", 18)
        pdf.cell(0, h_subtitle, self._safe(s["cert_subtitle"]), ln=True, align="C")
        y_cursor += h_subtitle

        pdf.set_y(y_cursor)
        self._set_font(pdf, "B", 34)
        pdf.cell(0, h_name, name_to_print, ln=True, align="C")
        y_cursor += h_name

        pdf.set_y(y_cursor)
        self._set_font(pdf, "", 14)
        pdf.cell(0, h_maktab, self._safe(s["cert_maktab_nomi"]), ln=True, align="C")
        y_cursor += h_maktab

        pdf.set_y(y_cursor)
        pdf.cell(0, h_matn, self._safe(s["cert_matn"]), ln=True, align="C")
        y_cursor += h_matn

        pdf.set_y(y_cursor)
        self._set_font(pdf, "B", 28)
        pdf.set_text_color(r, g, b)
        pdf.cell(0, h_ball, f"{score} BALL", ln=True, align="C")
        pdf.set_text_color(0, 0, 0)

        # Footer
        self._set_font(pdf, "I", 11)
        pdf.set_xy(20, 183)
        pdf.cell(100, 6, f"Sana: {date}", ln=0, align="L")
        pdf.set_xy(20, 189)
        pdf.cell(100, 6, f"Shaxsiy kod: {kod}", ln=0, align="L")

        self._add_qr(pdf, kod, PAGE_W, PAGE_H)

        out = os.path.join(self.output_dir, f"cert_{kod}.pdf")
        pdf.output(out)
        return out

    # ── QR-kod ───────────────────────────────────────────────────────────────

    def _add_qr(self, pdf: FPDF, kod: str, page_w: int, page_h: int) -> None:
        try:
            import qrcode as qrlib
            from config import VERIFY_BASE_URL
            url = f"{VERIFY_BASE_URL}/verify/{kod}"
            qr = qrlib.QRCode(version=2,
                               error_correction=qrlib.constants.ERROR_CORRECT_M,
                               box_size=6, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            qr_size = 22
            pdf.image(buf, x=page_w - qr_size - 14, y=page_h - qr_size - 13,
                      w=qr_size, h=qr_size)
        except Exception:
            pass

    # ── Preview ───────────────────────────────────────────────────────────────

    def generate_preview(self, pdf_path: str) -> str | None:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
            png_path = pdf_path.replace(".pdf", "_preview.png")
            pix.save(png_path)
            doc.close()
            return png_path
        except Exception:
            return None

    # ── Yordamchi ─────────────────────────────────────────────────────────────

    def _safe(self, text: str) -> str:
        return str(text or "") if self.unicode_font_ready else self._to_latin1_safe(text)

    def _set_font(self, pdf: FPDF, style: str, size: int):
        if self.unicode_font_ready:
            pdf.set_font(self.unicode_font_family, style if style in ("", "B") else "", size)
        else:
            pdf.set_font("Helvetica", style, size)

    def _configure_unicode_fonts(self, pdf: FPDF) -> bool:
        regular_candidates = [
            os.getenv("CERTIFICATE_FONT_REGULAR"),
            "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/local/share/fonts/DejaVuSans.ttf",
            "C:/Windows/Fonts/DejaVuSans.ttf",
        ]
        bold_candidates = [
            os.getenv("CERTIFICATE_FONT_BOLD"),
            "DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/local/share/fonts/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/DejaVuSans-Bold.ttf",
        ]
        rp = next((p for p in regular_candidates if p and os.path.exists(p)), None)
        bp = next((p for p in bold_candidates   if p and os.path.exists(p)), None)
        if not rp or not bp:
            return False
        pdf.add_font(self.unicode_font_family, "",  rp)
        pdf.add_font(self.unicode_font_family, "B", bp)
        return True

    @staticmethod
    def _to_latin1_safe(text) -> str:
        if text is None:
            return ""
        return str(text).translate(
            str.maketrans({"ʻ": "'", "ʼ": "'", "\u2018": "'", "\u2019": "'", "`": "'", "´": "'"})
        )
