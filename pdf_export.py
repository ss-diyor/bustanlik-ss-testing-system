import os
from datetime import datetime
from fpdf import FPDF
from database import (
    talaba_topish,
    talaba_natijalari,
    get_all_students,
    maktab_statistikasi,
    maktablar_ol,
    sinf_ol,
)

# DejaVu font yo'lini aniqlash (Unicode harflarni qo'llab-quvvatlash uchun)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_FONT_REGULAR = os.path.join(_BASE_DIR, "DejaVuSans.ttf")
_FONT_BOLD = os.path.join(_BASE_DIR, "DejaVuSans-Bold.ttf")

# Agar loyiha papkasida topilmasa, tizim fontlarini ishlatamiz
if not os.path.exists(_FONT_REGULAR):
    _FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
if not os.path.exists(_FONT_BOLD):
    _FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _make_pdf(orientation="P"):
    """Unicode fontli yangi FPDF obyekti yaratish"""
    pdf = FPDF(orientation=orientation)
    pdf.add_font("DejaVu", style="", fname=_FONT_REGULAR)
    pdf.add_font("DejaVu", style="B", fname=_FONT_BOLD)
    pdf.add_font("DejaVu", style="I", fname=_FONT_REGULAR)
    return pdf


class PDFExporter:
    def __init__(self):
        self.output_dir = "pdf_reports"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def create_student_pdf(self, talaba_kod):
        """O'quvchi uchun to'liq PDF hisobot"""
        talaba = talaba_topish(talaba_kod)
        if not talaba:
            return None

        pdf = _make_pdf()
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 16)

        # Sarlavha
        pdf.cell(
            0,
            10,
            f"O'quvchi hisoboti - {talaba['ismlar']}",
            ln=True,
            align="C",
        )
        pdf.ln(10)

        # Asosiy ma'lumotlar
        pdf.set_font("DejaVu", "", 12)
        pdf.cell(0, 8, f"Kod: {talaba['kod']}", ln=True)
        pdf.cell(0, 8, f"Sinf: {talaba['sinf']}", ln=True)
        pdf.cell(0, 8, f"Yo'nalish: {talaba.get('yonalish') or '-'}", ln=True)
        pdf.ln(10)

        # Natijalar jadvali
        natijalar = talaba_natijalari(talaba_kod)
        if natijalar:
            pdf.set_font("DejaVu", "B", 14)
            pdf.cell(0, 10, "Test natijalari:", ln=True)
            pdf.set_font("DejaVu", "", 10)

            # Jadval sarlavhalari
            pdf.cell(40, 8, "Sana", border=1)
            pdf.cell(30, 8, "Majburiy", border=1)
            pdf.cell(30, 8, "Asosiy 1", border=1)
            pdf.cell(30, 8, "Asosiy 2", border=1)
            pdf.cell(40, 8, "Umumiy ball", border=1, ln=True)

            for natija in natijalar:
                sana = natija["test_sanasi"].strftime("%d.%m.%Y")
                pdf.cell(40, 8, sana, border=1)
                pdf.cell(30, 8, str(natija["majburiy"]), border=1)
                pdf.cell(30, 8, str(natija["asosiy_1"]), border=1)
                pdf.cell(30, 8, str(natija["asosiy_2"]), border=1)
                pdf.cell(40, 8, str(natija["umumiy_ball"]), border=1, ln=True)

        # Statistika
        if natijalar:
            pdf.ln(10)
            pdf.set_font("DejaVu", "B", 14)
            pdf.cell(0, 10, "Statistika:", ln=True)
            pdf.set_font("DejaVu", "", 12)

            avg_ball = sum(n["umumiy_ball"] for n in natijalar) / len(
                natijalar
            )
            max_ball = max(n["umumiy_ball"] for n in natijalar)
            min_ball = min(n["umumiy_ball"] for n in natijalar)

            pdf.cell(0, 8, f"O'rtacha ball: {avg_ball:.1f}", ln=True)
            pdf.cell(0, 8, f"Eng yuqori ball: {max_ball}", ln=True)
            pdf.cell(0, 8, f"Eng past ball: {min_ball}", ln=True)
            pdf.cell(0, 8, f"Jami testlar: {len(natijalar)} ta", ln=True)

        # Sana
        pdf.ln(20)
        pdf.set_font("DejaVu", "I", 10)
        pdf.cell(
            0,
            8,
            f"Hisobot sanasi: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            ln=True,
        )

        filename = os.path.join(self.output_dir, f"student_{talaba_kod}.pdf")
        pdf.output(filename)
        return filename

    def create_maktab_statistika_pdf(self, maktab_id=None):
        """Maktab statistikasi uchun PDF"""
        stats = maktab_statistikasi(maktab_id)
        if not stats:
            return None

        # FIX: Landscape orientatsiya — jadval chetga chiqmasligi uchun
        # A4 Landscape: ~277mm foydalaniladigan kenglik
        # Ustunlar jami: 55+75+28+30+30+30 = 248mm < 277mm ✓
        pdf = _make_pdf(orientation="L")
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 16)

        # Sarlavha
        if maktab_id:
            maktablar = maktablar_ol()
            maktab = next((m for m in maktablar if m["id"] == maktab_id), None)
            title = f"{maktab['nomi'] if maktab else 'Maktab'} statistikasi"
        else:
            title = "Barcha maktablar statistikasi"

        pdf.cell(0, 10, title, ln=True, align="C")
        pdf.ln(10)

        # Jadval sarlavhalari — kengliklar landscape uchun moslashtirilgan
        pdf.set_font("DejaVu", "B", 11)
        pdf.cell(55, 8, "Maktab", border=1)
        pdf.cell(75, 8, "Sinf", border=1)
        pdf.cell(28, 8, "O'quvchilar", border=1)
        pdf.cell(30, 8, "O'rtacha", border=1)
        pdf.cell(30, 8, "Eng yuqori", border=1)
        pdf.cell(30, 8, "Eng past", border=1, ln=True)

        pdf.set_font("DejaVu", "", 10)
        for stat in stats:
            pdf.cell(55, 8, stat["maktab_nomi"], border=1)
            pdf.cell(75, 8, stat["sinf"], border=1)
            pdf.cell(28, 8, str(stat["oquvchilar_soni"]), border=1)
            pdf.cell(30, 8, f"{stat['ortacha_ball']:.1f}", border=1)
            pdf.cell(30, 8, f"{stat['eng_yuqori_ball']:.1f}", border=1)
            pdf.cell(30, 8, f"{stat['eng_past_ball']:.1f}", border=1, ln=True)

        # Umumiy statistika
        pdf.ln(10)
        pdf.set_font("DejaVu", "B", 14)
        pdf.cell(0, 10, "Umumiy ko'rsatkichlar:", ln=True)
        pdf.set_font("DejaVu", "", 12)

        jami_oquvchilar = sum(s["oquvchilar_soni"] for s in stats)
        umumiy_ortacha = (
            sum(s["ortacha_ball"] * s["oquvchilar_soni"] for s in stats)
            / jami_oquvchilar
            if jami_oquvchilar > 0
            else 0
        )

        pdf.cell(0, 8, f"Jami o'quvchilar: {jami_oquvchilar} ta", ln=True)
        pdf.cell(0, 8, f"Umumiy o'rtacha ball: {umumiy_ortacha:.1f}", ln=True)
        pdf.cell(
            0,
            8,
            f"Maktablar soni: {len(set(s['maktab_nomi'] for s in stats))} ta",
            ln=True,
        )

        # Sana
        pdf.ln(20)
        pdf.set_font("DejaVu", "I", 10)
        pdf.cell(
            0,
            8,
            f"Hisobot sanasi: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            ln=True,
        )

        filename = os.path.join(
            self.output_dir,
            f"maktab_stat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )
        pdf.output(filename)
        return filename

    def create_sinf_reyting_pdf(self, sinf=None, maktab_id=None):
        """Sinf reytingi uchun PDF.

        Parametrlar:
          sinf      — bitta sinf nomi (masalan "11-A - Bo'stonliq ITMA")
          maktab_id — maktab ID si: shu maktabdagi barcha sinflar
          (ikkalasi ham None bo'lsa — barcha sinflar)
        """
        if sinf:
            sinflar = [sinf]
            title = f"{sinf} sinf reytingi"
        elif maktab_id:
            from database import sinf_ol_batafsil
            batafsil = sinf_ol_batafsil()
            maktablar_list = maktablar_ol()
            maktab = next((m for m in maktablar_list if m["id"] == maktab_id), None)
            maktab_nomi = maktab["nomi"] if maktab else "Maktab"
            sinflar = [
                f"{s['nomi']} - {s['maktab_nomi']}"
                for s in batafsil
                if s["maktab_id"] == maktab_id
            ]
            title = f"{maktab_nomi} — barcha sinflar reytingi"
        else:
            sinflar = sinf_ol()
            title = "Barcha sinflar reytingi"

        if not sinflar:
            return None

        pdf = _make_pdf(orientation="L")
        pdf.add_page()
        pdf.set_font("DejaVu", "B", 16)

        pdf.cell(0, 10, title, ln=True, align="C")
        pdf.ln(10)

        from database import get_all_in_class

        for current_sinf in sinflar:
            talabalar = get_all_in_class(current_sinf)
            if not talabalar:
                continue

            pdf.set_font("DejaVu", "B", 14)
            pdf.cell(0, 10, f"{current_sinf} sinf:", ln=True)
            pdf.set_font("DejaVu", "B", 10)

            # Jadval sarlavhalari
            pdf.cell(12, 8, "No", border=1)
            pdf.cell(80, 8, "Ism", border=1)
            pdf.cell(35, 8, "Kod", border=1)
            pdf.cell(95, 8, "Yo'nalish", border=1)
            pdf.cell(25, 8, "Ball", border=1, ln=True)

            pdf.set_font("DejaVu", "", 9)
            for i, talaba in enumerate(talabalar, 1):
                pdf.cell(12, 8, str(i), border=1)
                pdf.cell(80, 8, talaba["ismlar"][:35], border=1)
                pdf.cell(35, 8, talaba["kod"], border=1)
                pdf.cell(95, 8, talaba.get("yonalish") or "-", border=1)
                pdf.cell(25, 8, str(talaba["umumiy_ball"]), border=1, ln=True)

            pdf.ln(5)

        # Sana
        pdf.ln(10)
        pdf.set_font("DejaVu", "I", 10)
        pdf.cell(
            0,
            8,
            f"Hisobot sanasi: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            ln=True,
        )

        filename = os.path.join(
            self.output_dir,
            f"reyting_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )
        pdf.output(filename)
        return filename
