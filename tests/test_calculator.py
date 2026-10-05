import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculator.core import add, subtract, multiply, divide, pow, sqrt, calculate


class OperationTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-2, 2), 0)
        self.assertEqual(add(0.5, 0.25), 0.75)

    def test_subtract(self):
        self.assertEqual(subtract(10, 4), 6)
        self.assertEqual(subtract(4, 10), -6)

    def test_multiply(self):
        self.assertEqual(multiply(3, 7), 21)
        self.assertEqual(multiply(-3, 7), -21)
        self.assertEqual(multiply(0, 100), 0)

    def test_divide(self):
        self.assertEqual(divide(10, 4), 2.5)
        self.assertEqual(divide(10, 2), 5)

    def test_divide_by_zero(self):
        self.assertRaises(ZeroDivisionError, divide, 1, 0)

    def test_pow(self):
        self.assertEqual(pow(2, 3), 8)
        self.assertEqual(pow(5, 0), 1)
        self.assertAlmostEqual(pow(9, 0.5), 3.0)
        self.assertAlmostEqual(pow(2, 0.5), 1.41421356, places=6)

    def test_pow_negative_base(self):
        self.assertRaises(ValueError, pow, -2, 0.5)

    def test_sqrt(self):
        self.assertAlmostEqual(sqrt(9), 3)
        self.assertAlmostEqual(sqrt(0), 0)
        self.assertAlmostEqual(sqrt(2), 1.41421356, places=6)

    def test_sqrt_negative(self):
        self.assertRaises(ValueError, sqrt, -1)


class CalculateTests(unittest.TestCase):
    def test_expressions(self):
        self.assertEqual(calculate("2 + 3"), 5)
        self.assertEqual(calculate("10 - 4"), 6)
        self.assertEqual(calculate("3 * 7"), 21)
        self.assertEqual(calculate("8 / 2"), 4)
        self.assertEqual(calculate("7 / 2"), 3.5)
        self.assertEqual(calculate("5 - 8"), -3)
        self.assertEqual(calculate(" 2 + 3 "), 5)
        self.assertEqual(calculate("2 pow 3"), 8)
        self.assertEqual(calculate("5 pow 2"), 25)
        self.assertAlmostEqual(calculate("2 pow 0.5"), 1.41421356, places=6)
        self.assertRaises(ValueError, calculate, "-2 pow 0.5")
        self.assertEqual(calculate("9 sqrt"), 3)
        self.assertEqual(calculate("sqrt 9"), 3)
        self.assertAlmostEqual(calculate("2 sqrt"), 1.41421356, places=6)
        self.assertRaises(ValueError, calculate, "-2 sqrt")

    def test_requires_three_tokens(self):
        self.assertRaises(ValueError, calculate, "2 +")
        self.assertRaises(ValueError, calculate, "2 + 3 4")

    def test_unknown_operator(self):
        self.assertRaises(ValueError, calculate, "2 % 3")
        self.assertRaises(ValueError, calculate, "2 ^ 3")

    def test_invalid_numbers(self):
        self.assertRaises(ValueError, calculate, "a + 3")
        self.assertRaises(ValueError, calculate, "2 + b")


if __name__ == "__main__":
    unittest.main()
