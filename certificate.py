from fpdf import FPDF
import os

class CertificateGenerator:
    def __init__(self):
        self.output_dir = "certificates"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate(self, full_name, score, date, kod):
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.add_page()
        
        # Border
        pdf.set_line_width(2)
        pdf.rect(10, 10, 277, 190)
        pdf.set_line_width(0.5)
        pdf.rect(12, 12, 273, 186)

        # Title
        pdf.set_font("Helvetica", "B", 40)
        pdf.cell(0, 40, "SERTIFIKAT", ln=True, align='C')
        
        pdf.set_font("Helvetica", "", 20)
        pdf.cell(0, 10, "Ushbu sertifikat bilan", ln=True, align='C')
        
        # Name
        pdf.set_font("Helvetica", "B", 35)
        pdf.cell(0, 30, full_name, ln=True, align='C')
        
        # Text
        pdf.set_font("Helvetica", "", 18)
        text = f"Bustanlik SS Testing System tomonidan o'tkazilgan testda"
        pdf.cell(0, 10, text, ln=True, align='C')
        
        pdf.set_font("Helvetica", "B", 25)
        pdf.cell(0, 20, f"{score} BALL", ln=True, align='C')
        
        pdf.set_font("Helvetica", "", 18)
        pdf.cell(0, 10, "to'plaganligi uchun taqdirlanadi.", ln=True, align='C')
        
        # Footer
        pdf.set_y(160)
        pdf.set_font("Helvetica", "I", 12)
        pdf.cell(0, 10, f"Sana: {date}", ln=0, align='L')
        pdf.set_x(200)
        pdf.cell(0, 10, f"ID: {kod}", ln=1, align='R')
        
        output_path = os.path.join(self.output_dir, f"cert_{kod}.pdf")
        pdf.output(output_path)
        return output_path
