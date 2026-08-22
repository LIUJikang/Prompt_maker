import unittest

from prompt_maker.workflow import legal_frame_count


class LegalFrameCountTests(unittest.TestCase):
    def test_frame_count_is_8n_plus_1(self):
        for seconds in (2, 5, 6.5, 10, 20):
            frames = legal_frame_count(seconds, 24)
            self.assertEqual((frames - 1) % 8, 0)

    def test_selects_nearest_valid_count(self):
        self.assertEqual(legal_frame_count(5, 24), 121)

    def test_never_returns_less_than_nine(self):
        self.assertGreaterEqual(legal_frame_count(0, 24), 9)


if __name__ == "__main__":
    unittest.main()
