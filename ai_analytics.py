import matplotlib.pyplot as plt
import numpy as np
import os
from database import talaba_natijalari, talaba_topish

class AIAnalytics:
    def __init__(self):
        self.output_dir = "analytics"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_radar_chart(self, last_result, kod):
        """O'quvchining fanlar bo'yicha bilim darajasini ko'rsatuvchi radar chart yaratadi."""
        # Maksimal ballar (DTM standarti bo'yicha)
        max_scores = {
            'majburiy': 30 * 1.1,  # 33.0
            'asosiy_1': 30 * 3.1,  # 93.0
            'asosiy_2': 30 * 2.1   # 63.0
        }
        
        categories = ['Majburiy fanlar', '1-Asosiy fan', '2-Asosiy fan']
        values = [
            (last_result['majburiy'] * 1.1 / max_scores['majburiy']) * 100,
            (last_result['asosiy_1'] * 3.1 / max_scores['asosiy_1']) * 100,
            (last_result['asosiy_2'] * 2.1 / max_scores['asosiy_2']) * 100
        ]
        
        # Radar chart uchun ma'lumotlarni tayyorlash
        N = len(categories)
        angles = [n / float(N) * 2 * np.pi for n in range(N)]
        values += values[:1]
        angles += angles[:1]
        
        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
        plt.xticks(angles[:-1], categories)
        
        ax.plot(angles, values, linewidth=2, linestyle='solid', color='#1f77b4')
        ax.fill(angles, values, color='#1f77b4', alpha=0.3)
        
        plt.title(f"Bilim darajasi tahlili (Foizda)", size=15, color='#1f77b4', y=1.1)
        
        chart_path = os.path.join(self.output_dir, f"radar_{kod}.png")
        plt.savefig(chart_path, bbox_inches='tight')
        plt.close()
        return chart_path

    def get_ai_recommendation(self, results):
        """O'quvchi natijalari asosida AI tavsiyalarini generatsiya qiladi."""
        if not results:
            return "Hali ma'lumotlar yetarli emas."
        
        last = results[0] # Oxirgi natija
        
        # Foizlarni hisoblash
        m_perc = (last['majburiy'] / 30) * 100
        a1_perc = (last['asosiy_1'] / 30) * 100
        a2_perc = (last['asosiy_2'] / 30) * 100
        
        recommendations = []
        
        # Kuchsiz nuqtalarni aniqlash
        low_score_threshold = 60
        if m_perc < low_score_threshold:
            recommendations.append("⚠️ Majburiy fanlardan natijangiz past. Kundalik 10 tadan test yechishni odat qiling.")
        
        if a1_perc < low_score_threshold:
            recommendations.append("⚠️ 1-asosiy fandan mavzularda bo'shliqlar bor. Nazariy qismni qayta ko'rib chiqing.")
            
        if a2_perc < low_score_threshold:
            recommendations.append("⚠️ 2-asosiy fandan ko'proq amaliyot kerak.")

        # Trendni aniqlash (agar kamida 2 ta natija bo'lsa)
        if len(results) >= 2:
            prev = results[1]
            diff = last['umumiy_ball'] - prev['umumiy_ball']
            if diff > 0:
                recommendations.append(f"📈 O'sish bor! Oldingi testga nisbatan +{diff:.1f} ball ko'proq to'pladingiz. Shu zaylda davom eting!")
            elif diff < 0:
                recommendations.append(f"📉 Pasayish kuzatildi ({diff:.1f} ball). Oxirgi mavzulardagi xatolaringizni tahlil qiling.")
        
        # Umumiy xulosa
        if not recommendations:
            recommendations.append("🌟 Ajoyib natija! Bilimingiz barqaror. Endi tezlik ustida ishlang.")
            
        return "\n".join(recommendations)

    async def get_full_analysis(self, kod):
        """Barcha tahlillarni birlashtirib qaytaradi."""
        results = talaba_natijalari(kod) # Eskidan yangiga keladi (student.py dagi tahlilga ko'ra)
        if not results:
            return None, "Natijalar topilmadi."
        
        # Natijalarni yangisidan eskiga tartiblaymiz tavsiya uchun
        sorted_results = sorted(results, key=lambda x: x['test_sanasi'], reverse=True)
        
        last_result = sorted_results[0]
        chart_path = self.generate_radar_chart(last_result, kod)
        recommendation = self.get_ai_recommendation(sorted_results)
        
        return chart_path, recommendation
