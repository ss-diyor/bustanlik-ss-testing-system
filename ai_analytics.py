import matplotlib.pyplot as plt
import os
from database import talaba_natijalari

class AIAnalytics:
    def __init__(self):
        self.output_dir = "analytics"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_bar_chart(self, last_result, kod):
        """O'quvchining fanlar bo'yicha bilim darajasini ko'rsatuvchi tushunarli Bar Chart yaratadi."""
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
        
        # Grafik ranglari (yashil, ko'k, to'q ko'k)
        colors = ['#4CAF50', '#2196F3', '#3F51B5']
        
        plt.figure(figsize=(10, 6))
        bars = plt.barh(categories, values, color=colors, height=0.6)
        
        # Har bir bar ustiga foizni yozish
        for bar, val in zip(bars, values):
            plt.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2, 
                    f'{val:.1f}%', va='center', fontweight='bold', size=12)
        
        plt.xlim(0, 115) # Foizlar 100 dan oshib ketmasligi uchun joy qoldiramiz
        plt.title(f"Fanlar bo'yicha o'zlashtirish ko'rsatkichi", size=16, fontweight='bold', pad=20)
        plt.xlabel("O'zlashtirish darajasi (%)", size=12)
        plt.grid(axis='x', linestyle='--', alpha=0.6)
        
        # Grafikni chiroyli ko'rinishga keltirish
        plt.tight_layout()
        
        chart_path = os.path.join(self.output_dir, f"analysis_{kod}.png")
        plt.savefig(chart_path, dpi=100)
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
            recommendations.append("⚠️ <b>Majburiy fanlar:</b> Natijangiz past. Kundalik 10 tadan test yechishni odat qiling.")
        
        if a1_perc < low_score_threshold:
            recommendations.append("⚠️ <b>1-asosiy fan:</b> Mavzularda bo'shliqlar bor. Nazariy qismni qayta ko'rib chiqing.")
            
        if a2_perc < low_score_threshold:
            recommendations.append("⚠️ <b>2-asosiy fan:</b> Ko'proq amaliyot va masalalar yechish kerak.")

        # Trendni aniqlash
        if len(results) >= 2:
            prev = results[1]
            diff = last['umumiy_ball'] - prev['umumiy_ball']
            if diff > 0:
                recommendations.append(f"📈 <b>O'sish:</b> Oldingi testga nisbatan +{diff:.1f} ball ko'proq to'pladingiz. Shu zaylda davom eting!")
            elif diff < 0:
                recommendations.append(f"📉 <b>Pasayish:</b> Natija {abs(diff):.1f} ballga kamaydi. Oxirgi mavzulardagi xatolaringizni tahlil qiling.")
        
        if not recommendations:
            recommendations.append("🌟 <b>Xulosa:</b> Ajoyib natija! Bilimingiz barqaror. Endi tezlik ustida ishlang.")
            
        return "\n".join(recommendations)

    async def get_full_analysis(self, kod):
        """Barcha tahlillarni birlashtirib qaytaradi."""
        results = talaba_natijalari(kod)
        if not results:
            return None, "Natijalar topilmadi."
        
        sorted_results = sorted(results, key=lambda x: x['test_sanasi'], reverse=True)
        
        last_result = sorted_results[0]
        chart_path = self.generate_bar_chart(last_result, kod)
        recommendation = self.get_ai_recommendation(sorted_results)
        
        return chart_path, recommendation
