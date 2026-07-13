"""DTM mock imtihoni uchun markazlashgan baholash qoidalari."""

DTM_EXAM_KEY = "DTM_MOCK"
DTM_MAX_SCORE = 189.0
DTM_SECTION_RULES = {
    "majburiy": {"label": "Majburiy fanlar", "questions": 30, "coefficient": 1.1},
    "asosiy_1": {"label": "1-asosiy fan", "questions": 30, "coefficient": 3.1},
    "asosiy_2": {"label": "2-asosiy fan", "questions": 30, "coefficient": 2.1},
}


def dtm_ball_hisobla(correct_counts: dict) -> float:
    """Bo'limlardagi to'g'ri javoblar sonidan 189 ballik natijani hisoblaydi."""
    total = 0.0
    for section_key, rule in DTM_SECTION_RULES.items():
        raw_value = correct_counts.get(section_key, 0)
        try:
            correct = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{section_key} to'g'ri javoblar soni raqam bo'lishi kerak") from exc

        if not 0 <= correct <= rule["questions"]:
            raise ValueError(
                f"{section_key} to'g'ri javoblar soni 0-{rule['questions']} oralig'ida bo'lishi kerak"
            )
        total += correct * rule["coefficient"]

    return round(total, 1)


def dtm_sections_natijasi(correct_counts: dict) -> dict:
    """Natija jadvalida saqlanadigan, audit qilish oson bo'lgan bo'lim qiymatlari."""
    result = {}
    for section_key, rule in DTM_SECTION_RULES.items():
        correct = int(correct_counts.get(section_key, 0))
        result[section_key] = {
            "value": correct,
            "max": rule["questions"],
            "label": rule["label"],
            "coefficient": rule["coefficient"],
            "score": round(correct * rule["coefficient"], 1),
        }
    return result
