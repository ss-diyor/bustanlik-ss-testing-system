from fpdf import FPDF
import os


class CertificateGenerator:
    def __init__(self):
        self.output_dir = "certificates"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        self.unicode_font_family = "DejaVuSans"
        self.unicode_font_ready = False

    def generate(self, full_name, score, date, kod):
        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.add_page()
        self.unicode_font_ready = self._configure_unicode_fonts(pdf)
        full_name_to_print = str(full_name or "")
        if not self.unicode_font_ready:
            # Core Helvetica cannot render all Uzbek apostrophe variants.
            full_name_to_print = self._to_latin1_safe(full_name_to_print)

        # Border
        pdf.set_line_width(2)
        pdf.rect(10, 10, 277, 190)
        pdf.set_line_width(0.5)
        pdf.rect(12, 12, 273, 186)

        # Title
        self._set_font(pdf, "B", 40)
        pdf.cell(0, 40, "SERTIFIKAT", ln=True, align="C")

        # Updated Header (Ushbu sertifikat bilan -> O'quvchining ismi va familyasi)
        self._set_font(pdf, "", 20)
        pdf.cell(0, 10, "O'quvchining ismi va familyasi", ln=True, align="C")

        # Name
        self._set_font(pdf, "B", 35)
        pdf.cell(0, 30, full_name_to_print, ln=True, align="C")

        # Main Text
        self._set_font(pdf, "", 16)
        text = "Bo'stonliq tumani ixtisoslashtirilgan maktabining"
        pdf.cell(0, 10, text, ln=True, align="C")
        text2 = "Bustanlik SS Testing System DTM imtihonida olingan ball"
        pdf.cell(0, 10, text2, ln=True, align="C")

        # Score
        self._set_font(pdf, "B", 25)
        pdf.cell(0, 20, f"{score} BALL", ln=True, align="C")

        # Removed "to'plaganligi uchun taqdirlanadi."

        # Footer (Date and Personal Code)
        pdf.set_y(165)
        self._set_font(pdf, "I", 12)

        # Footer Elements
        pdf.set_x(60)
        pdf.cell(80, 10, f"Sana: {date}", ln=0, align="L")

        pdf.set_x(160)
        pdf.cell(80, 10, f"Shaxsiy kod: {kod}", ln=1, align="R")

        output_path = os.path.join(self.output_dir, f"cert_{kod}.pdf")
        pdf.output(output_path)
        return output_path

    def _set_font(self, pdf: FPDF, style: str, size: int):
        if self.unicode_font_ready:
            # If italic face is not registered, fallback to normal face.
            style_to_use = style if style in ("", "B") else ""
            pdf.set_font(self.unicode_font_family, style_to_use, size)
            return
        pdf.set_font("Helvetica", style, size)

    def _configure_unicode_fonts(self, pdf: FPDF) -> bool:
        regular_candidates = [
            os.getenv("CERTIFICATE_FONT_REGULAR"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/local/share/fonts/DejaVuSans.ttf",
            "C:/Windows/Fonts/DejaVuSans.ttf",
        ]
        bold_candidates = [
            os.getenv("CERTIFICATE_FONT_BOLD"),
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
    def _to_latin1_safe(text):
        """Normalize Uzbek apostrophe variants for core Helvetica font."""
        if text is None:
            return ""
        normalized = str(text).translate(
            str.maketrans(
                {
                    "ʻ": "'",
                    "ʼ": "'",
                    "‘": "'",
                    "’": "'",
                    "`": "'",
                    "´": "'",
                }
            )
        )
        return normalized
