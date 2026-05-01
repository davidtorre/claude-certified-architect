# test_utils_new.py - Tests for calculate_percentage and sanitize_input

import unittest

from utils import calculate_percentage, sanitize_input


class TestCalculatePercentage(unittest.TestCase):

    def test_half(self):
        result = calculate_percentage(50, 100)
        self.assertEqual(result, 50.0)

    def test_full(self):
        result = calculate_percentage(100, 100)
        self.assertEqual(result, 100.0)

    def test_zero_part(self):
        result = calculate_percentage(0, 100)
        self.assertEqual(result, 0.0)

    def test_rounds_to_two_decimals(self):
        result = calculate_percentage(1, 3)
        self.assertEqual(result, 33.33)

    def test_greater_than_whole(self):
        result = calculate_percentage(150, 100)
        self.assertEqual(result, 150.0)

    def test_zero_whole_raises(self):
        with self.assertRaises(ZeroDivisionError):
            calculate_percentage(1, 0)


class TestSanitizeInput(unittest.TestCase):

    def test_removes_angle_brackets(self):
        result = sanitize_input("<script>alert(1)</script>")
        self.assertEqual(result, "scriptalert(1)/script")

    def test_plain_string_unchanged(self):
        result = sanitize_input("hello world")
        self.assertEqual(result, "hello world")

    def test_empty_string(self):
        result = sanitize_input("")
        self.assertEqual(result, "")

    def test_non_string_returns_empty(self):
        result = sanitize_input(123)
        self.assertEqual(result, "")

    def test_none_returns_empty(self):
        result = sanitize_input(None)
        self.assertEqual(result, "")

    def test_only_angle_brackets(self):
        result = sanitize_input("<<>>")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
