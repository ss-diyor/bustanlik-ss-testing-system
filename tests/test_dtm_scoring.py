import unittest

from dtm_scoring import DTM_MAX_SCORE, dtm_ball_hisobla, dtm_sections_natijasi


class DtmScoringTests(unittest.TestCase):
    def test_maximum_score_is_189(self):
        counts = {"majburiy": 30, "asosiy_1": 30, "asosiy_2": 30}
        self.assertEqual(dtm_ball_hisobla(counts), DTM_MAX_SCORE)

    def test_partial_score_uses_official_coefficients(self):
        counts = {"majburiy": 20, "asosiy_1": 15, "asosiy_2": 10}
        self.assertEqual(dtm_ball_hisobla(counts), 89.5)

    def test_missing_sections_are_zero(self):
        self.assertEqual(dtm_ball_hisobla({"asosiy_1": 1}), 3.1)

    def test_invalid_count_is_rejected(self):
        with self.assertRaises(ValueError):
            dtm_ball_hisobla({"majburiy": 31})

    def test_saved_sections_include_score_audit(self):
        result = dtm_sections_natijasi({"majburiy": 10, "asosiy_1": 20, "asosiy_2": 30})
        self.assertEqual(result["asosiy_1"]["score"], 62.0)
        self.assertEqual(result["asosiy_2"]["max"], 30)


if __name__ == "__main__":
    unittest.main()
