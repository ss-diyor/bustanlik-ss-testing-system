"""
Sertifikat generatori.
Barcha matn, rang va logo sozlamalari database'dan o'qiladi.
Admin panelidan o'zgartirish mumkin (cert_admin.py).
"""
from __future__ import annotations

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
}


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

    # ── Konstruktorlar ────────────────────────────────────────────────────────

    @classmethod
    def from_db(cls) -> "CertificateGenerator":
        """Database'dagi sozlamalar bilan generator yaratadi."""
        try:
            from database import get_setting
            settings = {
                key: get_setting(key, default)
                for key, default in CERT_DEFAULTS.items()
            }
        except Exception:
            settings = {}
        return cls(settings)

    # ── Asosiy metod ──────────────────────────────────────────────────────────

    def generate(
        self,
        full_name: str,
        score: int | float | str,
        date: str,
        kod: str,
    ) -> str:
        s = self._s
        r = _to_int(s["cert_rang_r"], 0)
        g = _to_int(s["cert_rang_g"], 0)
        b = _to_int(s["cert_rang_b"], 128)

        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.add_page()
        self.unicode_font_ready = self._configure_unicode_fonts(pdf)

        name_to_print = str(full_name or "")
        if not self.unicode_font_ready:
            name_to_print = self._to_latin1_safe(name_to_print)

        # ── Chegara ───────────────────────────────────────────────────────────
        pdf.set_draw_color(r, g, b)
        pdf.set_line_width(3)
        pdf.rect(8, 8, 281, 194)
        pdf.set_line_width(0.8)
        pdf.rect(11, 11, 275, 188)

        y_cursor = 14

        # ── Logo ──────────────────────────────────────────────────────────────
        logo_path = s.get("cert_logo_path", "").strip()
        if logo_path and os.path.exists(logo_path):
            try:
                logo_w, logo_h = 25, 25
                logo_x = (297 - logo_w) / 2
                pdf.image(logo_path, x=logo_x, y=y_cursor, w=logo_w, h=logo_h)
                y_cursor += logo_h + 4
            except Exception:
                pass

        # ── Sarlavha ──────────────────────────────────────────────────────────
        pdf.set_y(y_cursor)
        pdf.set_text_color(r, g, b)
        self._set_font(pdf, "B", 42)
        pdf.cell(0, 18, self._safe(s["cert_sarlavha"]), ln=True, align="C")
        pdf.set_text_color(0, 0, 0)

        # ── Subtitle ─────────────────────────────────────────────────────────
        self._set_font(pdf, "", 18)
        pdf.cell(0, 8, self._safe(s["cert_subtitle"]), ln=True, align="C")

        # ── O'quvchi ismi ─────────────────────────────────────────────────────
        self._set_font(pdf, "B", 34)
        pdf.cell(0, 22, name_to_print, ln=True, align="C")

        # ── Maktab nomi ───────────────────────────────────────────────────────
        self._set_font(pdf, "", 15)
        pdf.cell(0, 8, self._safe(s["cert_maktab_nomi"]), ln=True, align="C")

        # ── Qo'shimcha matn ───────────────────────────────────────────────────
        pdf.cell(0, 8, self._safe(s["cert_matn"]), ln=True, align="C")

        # ── Ball ─────────────────────────────────────────────────────────────
        self._set_font(pdf, "B", 28)
        pdf.set_text_color(r, g, b)
        pdf.cell(0, 16, f"{score} BALL", ln=True, align="C")
        pdf.set_text_color(0, 0, 0)

        # ── Footer ────────────────────────────────────────────────────────────
        pdf.set_y(172)
        self._set_font(pdf, "I", 11)
        pdf.set_x(50)
        pdf.cell(90, 10, f"Sana: {date}", ln=0, align="L")
        pdf.set_x(160)
        pdf.cell(90, 10, f"Shaxsiy kod: {kod}", ln=1, align="R")

        output_path = os.path.join(self.output_dir, f"cert_{kod}.pdf")
        pdf.output(output_path)
        return output_path

    # ── Yordamchi metodlar ────────────────────────────────────────────────────

    def _safe(self, text: str) -> str:
        if self.unicode_font_ready:
            return str(text or "")
        return self._to_latin1_safe(text)

    def _set_font(self, pdf: FPDF, style: str, size: int):
        if self.unicode_font_ready:
            style_to_use = style if style in ("", "B") else ""
            pdf.set_font(self.unicode_font_family, style_to_use, size)
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
        regular_path = next(
            (p for p in regular_candidates if p and os.path.exists(p)), None
        )
        bold_path = next(
            (p for p in bold_candidates if p and os.path.exists(p)), None
        )
        if not regular_path or not bold_path:
            return False
        pdf.add_font(self.unicode_font_family, "", regular_path)
        pdf.add_font(self.unicode_font_family, "B", bold_path)
        return True

    @staticmethod
    def _to_latin1_safe(text) -> str:
        if text is None:
            return ""
        return str(text).translate(
            str.maketrans(
                {"ʻ": "'", "ʼ": "'", "\u2018": "'", "\u2019": "'", "`": "'", "´": "'"}
            )
        )
