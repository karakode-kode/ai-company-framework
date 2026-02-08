import unittest

from calculator import add, subtract, multiply, divide


class TestAdd(unittest.TestCase):
    def test_positive_numbers(self):
        self.assertEqual(add(2, 3), 5)

    def test_negative_numbers(self):
        self.assertEqual(add(-1, -1), -2)

    def test_mixed_signs(self):
        self.assertEqual(add(-1, 1), 0)


class TestSubtract(unittest.TestCase):
    def test_positive_numbers(self):
        self.assertEqual(subtract(5, 3), 2)

    def test_negative_result(self):
        self.assertEqual(subtract(3, 5), -2)

    def test_same_numbers(self):
        self.assertEqual(subtract(4, 4), 0)


class TestMultiply(unittest.TestCase):
    def test_positive_numbers(self):
        self.assertEqual(multiply(3, 4), 12)

    def test_by_zero(self):
        self.assertEqual(multiply(5, 0), 0)

    def test_negative_numbers(self):
        self.assertEqual(multiply(-2, -3), 6)


class TestDivide(unittest.TestCase):
    def test_exact_division(self):
        self.assertEqual(divide(10, 2), 5)

    def test_float_result(self):
        self.assertAlmostEqual(divide(7, 2), 3.5)

    def test_divide_by_zero(self):
        with self.assertRaises(ValueError):
            divide(1, 0)

    def test_negative_division(self):
        self.assertEqual(divide(-6, 3), -2)


if __name__ == "__main__":
    unittest.main()
