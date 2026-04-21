import os
from datetime import datetime
from fpdf import FPDF
from database import (
    talaba_topish, talaba_natijalari, get_all_students, 
    maktab_statistikasi, maktablar_ol, sinf_ol
)

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

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        
        # Sarlavha
        pdf.cell(0, 10, f"O'quvchi hisoboti - {talaba['ismlar']}", ln=True, align='C')
        pdf.ln(10)
        
        # Asosiy ma'lumotlar
        pdf.set_font("Arial", '', 12)
        pdf.cell(0, 8, f"Kod: {talaba['kod']}", ln=True)
        pdf.cell(0, 8, f"Sinf: {talaba['sinf']}", ln=True)
        pdf.cell(0, 8, f"Yo'nalish: {talaba.get('yonalish') or '-'}", ln=True)
        pdf.ln(10)
        
        # Natijalar jadvali
        natijalar = talaba_natijalari(talaba_kod)
        if natijalar:
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, "Test natijalari:", ln=True)
            pdf.set_font("Arial", '', 10)
            
            # Jadval sarlavhalari
            pdf.cell(40, 8, "Sana", border=1)
            pdf.cell(30, 8, "Majburiy", border=1)
            pdf.cell(30, 8, "Asosiy 1", border=1)
            pdf.cell(30, 8, "Asosiy 2", border=1)
            pdf.cell(40, 8, "Umumiy ball", border=1, ln=True)
            
            for natija in natijalar:
                sana = natija['test_sanasi'].strftime('%d.%m.%Y')
                pdf.cell(40, 8, sana, border=1)
                pdf.cell(30, 8, str(natija['majburiy']), border=1)
                pdf.cell(30, 8, str(natija['asosiy_1']), border=1)
                pdf.cell(30, 8, str(natija['asosiy_2']), border=1)
                pdf.cell(40, 8, str(natija['umumiy_ball']), border=1, ln=True)
        
        # Statistika
        if natijalar:
            pdf.ln(10)
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, "Statistika:", ln=True)
            pdf.set_font("Arial", '', 12)
            
            avg_ball = sum(n['umumiy_ball'] for n in natijalar) / len(natijalar)
            max_ball = max(n['umumiy_ball'] for n in natijalar)
            min_ball = min(n['umumiy_ball'] for n in natijalar)
            
            pdf.cell(0, 8, f"O'rtacha ball: {avg_ball:.1f}", ln=True)
            pdf.cell(0, 8, f"Eng yuqori ball: {max_ball}", ln=True)
            pdf.cell(0, 8, f"Eng past ball: {min_ball}", ln=True)
            pdf.cell(0, 8, f"Jami testlar: {len(natijalar)} ta", ln=True)
        
        # Sana
        pdf.ln(20)
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(0, 8, f"Hisobot sanasi: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True)
        
        filename = os.path.join(self.output_dir, f"student_{talaba_kod}.pdf")
        pdf.output(filename)
        return filename

    def create_maktab_statistika_pdf(self, maktab_id=None):
        """Maktab statistikasi uchun PDF"""
        stats = maktab_statistikasi(maktab_id)
        if not stats:
            return None

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        
        # Sarlavha
        if maktab_id:
            maktablar = maktablar_ol()
            maktab = next((m for m in maktablar if m["id"] == maktab_id), None)
            title = f"{maktab['nomi'] if maktab else 'Maktab'} statistikasi"
        else:
            title = "Barcha maktablar statistikasi"
        
        pdf.cell(0, 10, title, ln=True, align='C')
        pdf.ln(10)
        
        # Jadval
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(55, 8, "Maktab", border=1)
        pdf.cell(70, 8, "Sinf", border=1)
        pdf.cell(28, 8, "O'quvchilar", border=1)
        pdf.cell(30, 8, "O'rtacha", border=1)
        pdf.cell(30, 8, "Eng yuqori", border=1)
        pdf.cell(30, 8, "Eng past", border=1, ln=True)
        
        pdf.set_font("Arial", '', 9)
        for stat in stats:
            pdf.cell(55, 8, stat['maktab_nomi'], border=1)
            pdf.cell(70, 8, stat['sinf'], border=1)
            pdf.cell(28, 8, str(stat['oquvchilar_soni']), border=1)
            pdf.cell(30, 8, f"{stat['ortacha_ball']:.1f}", border=1)
            pdf.cell(30, 8, f"{stat['eng_yuqori_ball']:.1f}", border=1)
            pdf.cell(30, 8, f"{stat['eng_past_ball']:.1f}", border=1, ln=True)
        
        # Umumiy statistika
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "Umumiy ko'rsatkichlar:", ln=True)
        pdf.set_font("Arial", '', 12)
        
        jami_oquvchilar = sum(s['oquvchilar_soni'] for s in stats)
        umumiy_ortacha = sum(s['ortacha_ball'] * s['oquvchilar_soni'] for s in stats) / jami_oquvchilar if jami_oquvchilar > 0 else 0
        
        pdf.cell(0, 8, f"Jami o'quvchilar: {jami_oquvchilar} ta", ln=True)
        pdf.cell(0, 8, f"Umumiy o'rtacha ball: {umumiy_ortacha:.1f}", ln=True)
        pdf.cell(0, 8, f"Maktablar soni: {len(set(s['maktab_nomi'] for s in stats))} ta", ln=True)
        
        # Sana
        pdf.ln(20)
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(0, 8, f"Hisobot sanasi: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True)
        
        filename = os.path.join(self.output_dir, f"maktab_stat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        pdf.output(filename)
        return filename

    def create_sinf_reyting_pdf(self, sinf=None):
        """Sinf reytingi uchun PDF"""
        sinflar = sinf_ol()
        if sinf and sinf not in sinflar:
            sinflar = [sinf] if sinf in sinf_ol() else sinflar
        elif not sinf:
            sinflar = sinflar
        
        # Reyting jadvalida yo'nalish matni to'liq ko'rinishi uchun landscape
        pdf = FPDF(orientation='L')
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        
        title = f"{sinf} sinf reytingi" if sinf else "Barcha sinflar reytingi"
        pdf.cell(0, 10, title, ln=True, align='C')
        pdf.ln(10)
        
        from database import get_all_in_class
        
        for current_sinf in sinflar:
            talabalar = get_all_in_class(current_sinf)
            if not talabalar:
                continue
            
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, f"{current_sinf} sinf:", ln=True)
            pdf.set_font("Arial", 'B', 10)
            
            # Jadval sarlavhalari
            pdf.cell(12, 8, "No", border=1)
            pdf.cell(80, 8, "Ism", border=1)
            pdf.cell(35, 8, "Kod", border=1)
            pdf.cell(95, 8, "Yo'nalish", border=1)
            pdf.cell(25, 8, "Ball", border=1, ln=True)
            
            pdf.set_font("Arial", '', 9)
            for i, talaba in enumerate(talabalar[:20], 1):  # Top 20
                pdf.cell(12, 8, str(i), border=1)
                pdf.cell(80, 8, talaba['ismlar'][:35], border=1)
                pdf.cell(35, 8, talaba['kod'], border=1)
                pdf.cell(95, 8, talaba.get('yonalish') or '-', border=1)
                pdf.cell(25, 8, str(talaba['umumiy_ball']), border=1, ln=True)
            
            pdf.ln(5)
        
        # Sana
        pdf.ln(10)
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(0, 8, f"Hisobot sanasi: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True)
        
        filename = os.path.join(self.output_dir, f"reyting_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        pdf.output(filename)
        return filename
