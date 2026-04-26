import matplotlib.pyplot as plt
import os
import json
import asyncio
import urllib.request
from database import talaba_natijalari
from config import AI_API_KEY, AI_BASE_URL, AI_MODEL


class AIAnalytics:
    def __init__(self):
        self.output_dir = "analytics"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_bar_chart(self, last_result, kod):
        """O'quvchining fanlar bo'yicha bilim darajasini ko'rsatuvchi tushunarli Bar Chart yaratadi."""
        # Maksimal ballar (DTM standarti bo'yicha)
        max_scores = {
            "majburiy": 30 * 1.1,  # 33.0
            "asosiy_1": 30 * 3.1,  # 93.0
            "asosiy_2": 30 * 2.1,  # 63.0
        }

        categories = ["Majburiy fanlar", "1-Asosiy fan", "2-Asosiy fan"]
        values = [
            (last_result["majburiy"] * 1.1 / max_scores["majburiy"]) * 100,
            (last_result["asosiy_1"] * 3.1 / max_scores["asosiy_1"]) * 100,
            (last_result["asosiy_2"] * 2.1 / max_scores["asosiy_2"]) * 100,
        ]

        # Grafik ranglari (yashil, ko'k, to'q ko'k)
        colors = ["#4CAF50", "#2196F3", "#3F51B5"]

        plt.figure(figsize=(10, 6))
        bars = plt.barh(categories, values, color=colors, height=0.6)

        # Har bir bar ustiga foizni yozish
        for bar, val in zip(bars, values):
            plt.text(
                bar.get_width() + 2,
                bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%",
                va="center",
                fontweight="bold",
                size=12,
            )

        plt.xlim(
            0, 115
        )  # Foizlar 100 dan oshib ketmasligi uchun joy qoldiramiz
        plt.title(
            f"Fanlar bo'yicha o'zlashtirish ko'rsatkichi",
            size=16,
            fontweight="bold",
            pad=20,
        )
        plt.xlabel("O'zlashtirish darajasi (%)", size=12)
        plt.grid(axis="x", linestyle="--", alpha=0.6)

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

        last = results[0]  # Oxirgi natija

        # Foizlarni hisoblash
        m_perc = (last["majburiy"] / 30) * 100
        a1_perc = (last["asosiy_1"] / 30) * 100
        a2_perc = (last["asosiy_2"] / 30) * 100

        recommendations = []

        # Kuchsiz nuqtalarni aniqlash
        low_score_threshold = 60
        if m_perc < low_score_threshold:
            recommendations.append(
                "⚠️ <b>Majburiy fanlar:</b> Natijangiz past. Kundalik 10 tadan test yechishni odat qiling."
            )

        if a1_perc < low_score_threshold:
            recommendations.append(
                "⚠️ <b>1-asosiy fan:</b> Mavzularda bo'shliqlar bor. Nazariy qismni qayta ko'rib chiqing."
            )

        if a2_perc < low_score_threshold:
            recommendations.append(
                "⚠️ <b>2-asosiy fan:</b> Ko'proq amaliyot va masalalar yechish kerak."
            )

        # Trendni aniqlash
        if len(results) >= 2:
            prev = results[1]
            diff = last["umumiy_ball"] - prev["umumiy_ball"]
            if diff > 0:
                recommendations.append(
                    f"📈 <b>O'sish:</b> Oldingi testga nisbatan +{diff:.1f} ball ko'proq to'pladingiz. Shu zaylda davom eting!"
                )
            elif diff < 0:
                recommendations.append(
                    f"📉 <b>Pasayish:</b> Natija {abs(diff):.1f} ballga kamaydi. Oxirgi mavzulardagi xatolaringizni tahlil qiling."
                )

        if not recommendations:
            recommendations.append(
                "🌟 <b>Xulosa:</b> Ajoyib natija! Bilimingiz barqaror. Endi tezlik ustida ishlang."
            )

        return "\n".join(recommendations)

    def _build_prompt(self, results):
        last = results[0]
        prev = results[1] if len(results) > 1 else None

        trend = None
        if prev:
            trend = round(last["umumiy_ball"] - prev["umumiy_ball"], 2)

        system = (
            "Sen ta'lim analitigi sifatida ishlaysan. "
            "MUHIM: 'majburiy_togri', 'asosiy_1_togri', 'asosiy_2_togri' maydonlari "
            "BALL EMAS — har bir bo'limda o'quvchi nechta savolga TO'G'RI javob berganini bildiradi (maksimum 30 ta). "
            "Hisoblangan yakuniy ball esa 'hisoblangan_umumiy_ball' maydonida ko'rsatilgan. "
            "Tahlil yozganingda doim 'to'g'ri javoblar soni' va 'hisoblangan ball'ni farqlab ishlat. "
            "Javobni o'zbek tilida, aniq va amaliy yoz. "
            "Outputni oddiy HTML-safe matn sifatida qaytar (faqat <b> tegidan foydalansang bo'ladi). "
            "Jami javob 800 so'zdan oshmasin. "
            "Qat'iy 4 bo'lim: "
            "1) Qisqa xulosa (2-3 gap), "
            "2) Kuchsiz nuqtalar (har biri 1 qator), "
            "3) Kuchli nuqtalar (har biri 1 qator), "
            "4) 7 kunlik reja (har kun 1 qator, aniq vazifa)."
        )
        user = {
            "oxirgi_natija": {
                "majburiy_togri_javoblar": last["majburiy"],
                "asosiy_1_togri_javoblar": last["asosiy_1"],
                "asosiy_2_togri_javoblar": last["asosiy_2"],
                "hisoblangan_umumiy_ball": last["umumiy_ball"],
            },
            "trend_ball": trend,
            "oxirgi_5_test": [
                {
                    "majburiy_togri_javoblar": r["majburiy"],
                    "asosiy_1_togri_javoblar": r["asosiy_1"],
                    "asosiy_2_togri_javoblar": r["asosiy_2"],
                    "hisoblangan_umumiy_ball": r["umumiy_ball"],
                    "test_sanasi": str(r["test_sanasi"]),
                }
                for r in results[:5]
            ],
        }
        return system, user

    def _call_llm_sync(self, results):
        system_text, user_payload = self._build_prompt(results)
        url = AI_BASE_URL.rstrip("/") + "/chat/completions"
        payload = {
            "model": AI_MODEL,
            "temperature": 0.3,
            "max_tokens": 1200,
            "messages": [
                {"role": "system", "content": system_text},
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {AI_API_KEY}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            response_body = resp.read().decode("utf-8")
        parsed = json.loads(response_body)
        return parsed["choices"][0]["message"]["content"].strip()

    async def get_llm_recommendation(self, results):
        if not AI_API_KEY:
            return None
        try:
            return await asyncio.to_thread(self._call_llm_sync, results)
        except Exception:
            return None

    async def get_full_analysis(self, kod):
        """Barcha tahlillarni birlashtirib qaytaradi."""
        results = talaba_natijalari(kod)
        if not results:
            return None, "Natijalar topilmadi."

        sorted_results = sorted(
            results, key=lambda x: x["test_sanasi"], reverse=True
        )

        last_result = sorted_results[0]
        chart_path = self.generate_bar_chart(last_result, kod)
        recommendation = await self.get_llm_recommendation(sorted_results)
        if not recommendation:
            recommendation = self.get_ai_recommendation(sorted_results)

        return chart_path, recommendation
