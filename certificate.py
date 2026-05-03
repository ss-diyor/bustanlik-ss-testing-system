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
        sinf: str = "",
        maktab: str = "",
    ) -> str:
        s = self._s
        r = _to_int(s["cert_rang_r"], 0)
        g = _to_int(s["cert_rang_g"], 0)
        b = _to_int(s["cert_rang_b"], 128)

        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=False)   # 1 betdan oshmasin
        pdf.add_page()
        self.unicode_font_ready = self._configure_unicode_fonts(pdf)

        name_to_print = str(full_name or "")
        if not self.unicode_font_ready:
            name_to_print = self._to_latin1_safe(name_to_print)

        # ── Sahifa o'lchamlari (Landscape A4) ────────────────────────────────
        PAGE_W, PAGE_H = 297, 210   # mm

        # ── Tarkib balandligini hisoblash (vertikal markazlash uchun) ─────────
        logo_path = s.get("cert_logo_path", "").strip()
        has_logo   = bool(logo_path and os.path.exists(logo_path))
        has_school = bool(sinf or maktab)

        logo_h_mm   = 25 if has_logo else 0
        logo_gap    = 4  if has_logo else 0
        h_sarlavha  = 18   # SERTIFIKAT (42pt)
        h_subtitle  = 8    # subtitle
        h_name      = 20   # ism (34pt)
        h_school    = 7    if has_school else 0
        h_maktab    = 8    # maktab nomi (shablondan)
        h_matn      = 7    # qo'shimcha matn
        h_ball      = 15   # ball

        CONTENT_H = (logo_h_mm + logo_gap
                     + h_sarlavha + h_subtitle + h_name
                     + h_school + h_maktab + h_matn + h_ball)

        BORDER    = 14     # chegara va bo'sh joy (yuqori + pastki)
        FOOTER_H  = 10     # footer uchun joy
        usable_h  = PAGE_H - BORDER * 2 - FOOTER_H

        # Tarkibni vertikal markazga joylashtirish
        y_cursor = BORDER + max(0, (usable_h - CONTENT_H) / 2)

        # ── Chegara ───────────────────────────────────────────────────────────
        pdf.set_draw_color(r, g, b)
        pdf.set_line_width(3)
        pdf.rect(8, 8, 281, 194)
        pdf.set_line_width(0.8)
        pdf.rect(11, 11, 275, 188)

        # ── Logo ──────────────────────────────────────────────────────────────
        if has_logo:
            try:
                logo_w = 25
                logo_x = (PAGE_W - logo_w) / 2
                # PNG transparency ni to'g'ri ko'rsatish uchun link=False,
                # fpdf2 RGBA PNG ni natively qo'llab-quvvatlaydi
                pdf.image(logo_path, x=logo_x, y=y_cursor, w=logo_w, h=logo_h_mm)
                y_cursor += logo_h_mm + logo_gap
            except Exception:
                pass

        # ── Sarlavha ──────────────────────────────────────────────────────────
        pdf.set_y(y_cursor)
        pdf.set_text_color(r, g, b)
        self._set_font(pdf, "B", 42)
        pdf.cell(0, h_sarlavha, self._safe(s["cert_sarlavha"]), ln=True, align="C")
        pdf.set_text_color(0, 0, 0)
        y_cursor += h_sarlavha

        # ── Subtitle ─────────────────────────────────────────────────────────
        pdf.set_y(y_cursor)
        self._set_font(pdf, "", 18)
        pdf.cell(0, h_subtitle, self._safe(s["cert_subtitle"]), ln=True, align="C")
        y_cursor += h_subtitle

        # ── O'quvchi ismi ─────────────────────────────────────────────────────
        pdf.set_y(y_cursor)
        self._set_font(pdf, "B", 34)
        pdf.cell(0, h_name, name_to_print, ln=True, align="C")
        y_cursor += h_name

        # ── Sinf va Maktab (agar mavjud bo'lsa) ──────────────────────────────
        if has_school:
            pdf.set_y(y_cursor)
            self._set_font(pdf, "", 13)
            pdf.set_text_color(80, 80, 80)
            parts = []
            if maktab:
                parts.append(self._safe(maktab))
            if sinf:
                parts.append(f"{self._safe(sinf)}-sinf")
            pdf.cell(0, h_school, "  •  ".join(parts), ln=True, align="C")
            pdf.set_text_color(0, 0, 0)
            y_cursor += h_school

        # ── Maktab nomi (shablondan) ──────────────────────────────────────────
        pdf.set_y(y_cursor)
        self._set_font(pdf, "", 14)
        pdf.cell(0, h_maktab, self._safe(s["cert_maktab_nomi"]), ln=True, align="C")
        y_cursor += h_maktab

        # ── Qo'shimcha matn ───────────────────────────────────────────────────
        pdf.set_y(y_cursor)
        pdf.cell(0, h_matn, self._safe(s["cert_matn"]), ln=True, align="C")
        y_cursor += h_matn

        # ── Ball ─────────────────────────────────────────────────────────────
        pdf.set_y(y_cursor)
        self._set_font(pdf, "B", 28)
        pdf.set_text_color(r, g, b)
        pdf.cell(0, h_ball, f"{score} BALL", ln=True, align="C")
        pdf.set_text_color(0, 0, 0)

        # ── Footer ────────────────────────────────────────────────────────────
        pdf.set_y(PAGE_H - 14)
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
