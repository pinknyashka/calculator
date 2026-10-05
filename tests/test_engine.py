# -*- coding: utf-8 -*-
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculator.engine import CalculatorEngine


def press_sequence(engine, seq):
    for ch in seq:
        if ch.isdigit():
            engine.press_digit(ch)
        elif ch == ".":
            engine.press_dot()
        elif ch in "+-*/":
            engine.press_operator(ch)
        elif ch == "^":
            engine.press_operator("pow")
        elif ch == "r":
            engine.press_operator("sqrt")
        elif ch == "=":
            engine.press_equals()
    return engine


class EngineTests(unittest.TestCase):
    def test_digit_entry(self):
        e = CalculatorEngine()
        press_sequence(e, "123")
        self.assertEqual(e.display_value(), "123")
        self.assertEqual(e.formula_value(), "")

    def test_simple_add(self):
        e = press_sequence(CalculatorEngine(), "3+4=")
        self.assertEqual(e.formula_value(), "3 + 4 = 7")
        self.assertEqual(e.display_value(), "7")

    def test_float_result(self):
        e = press_sequence(CalculatorEngine(), "7/2=")
        self.assertEqual(e.formula_value(), "7 / 2 = 3.5")
        self.assertEqual(e.display_value(), "3.5")

    def test_chained_operations(self):
        e = press_sequence(CalculatorEngine(), "2+3*2=")
        self.assertEqual(e.display_value(), "10")
        self.assertEqual(e.formula_value(), "5 * 2 = 10")

    def test_operator_change(self):
        e = press_sequence(CalculatorEngine(), "5+-")
        self.assertEqual(e.formula_value(), "5 -")

    def test_continue_after_equals(self):
        e = press_sequence(CalculatorEngine(), "2+2=+3=")
        self.assertEqual(e.display_value(), "7")
        self.assertEqual(e.formula_value(), "4 + 3 = 7")

    def test_digit_after_equals_starts_fresh(self):
        e = press_sequence(CalculatorEngine(), "2+2=5")
        self.assertEqual(e.display_value(), "5")
        self.assertEqual(e.formula_value(), "")

    def test_divide_by_zero(self):
        e = press_sequence(CalculatorEngine(), "5/0=")
        self.assertEqual(e.display_value(), u"Ошибка: деление на ноль")
        self.assertEqual(e.formula_value(), "")
        e.press_digit("7")
        self.assertEqual(e.display_value(), "7")

    def test_backspace(self):
        e = CalculatorEngine()
        press_sequence(e, "123")
        e.press_backspace()
        self.assertEqual(e.display_value(), "12")

    def test_clear(self):
        e = press_sequence(CalculatorEngine(), "1+2=")
        e.press_clear()
        self.assertEqual(e.display_value(), "0")
        self.assertEqual(e.formula_value(), "")

    def test_decimal(self):
        e = press_sequence(CalculatorEngine(), "0.5+0.25=")
        self.assertEqual(e.display_value(), "0.75")

    def test_dot_always_once(self):
        e = CalculatorEngine()
        press_sequence(e, ".")
        self.assertEqual(e.entry, "0.")
        e.press_dot()
        self.assertEqual(e.entry, "0.")

    def test_max_digits(self):
        e = CalculatorEngine()
        press_sequence(e, "1234567890123456")
        self.assertEqual(len(e.entry), 15)

    def test_empty_equals_noop(self):
        e = CalculatorEngine()
        e.press_equals()
        self.assertEqual(e.display_value(), "0")

    def test_negative_result(self):
        e = press_sequence(CalculatorEngine(), "5-8=")
        self.assertEqual(e.formula_value(), "5 - 8 = -3")
        self.assertEqual(e.display_value(), "-3")

    def test_pow(self):
        e = press_sequence(CalculatorEngine(), "2^3=")
        self.assertEqual(e.formula_value(), "2 pow 3 = 8")
        self.assertEqual(e.display_value(), "8")

    def test_pow_fractional_exponent(self):
        e = CalculatorEngine()
        press_sequence(e, "9")
        e.press_operator("pow")
        press_sequence(e, "0.5=")
        self.assertEqual(e.display_value(), "3")

    def test_pow_negative_base(self):
        e = CalculatorEngine()
        press_sequence(e, "5-8=")
        e.press_operator("pow")
        press_sequence(e, "0.5=")
        self.assertEqual(e.display_value(), u"Ошибка: отрицательное основание")
        self.assertEqual(e.formula_value(), "")
        e.press_digit("7")
        self.assertEqual(e.display_value(), "7")

    def test_sqrt(self):
        e = press_sequence(CalculatorEngine(), "9r")
        self.assertEqual(e.display_value(), "3")
        self.assertEqual(e.formula_value(), "sqrt 9 = 3")

    def test_sqrt_fractional_result(self):
        e = press_sequence(CalculatorEngine(), "2r")
        self.assertAlmostEqual(float(e.display_value()), 1.41421356, places=6)
        self.assertTrue(e.formula_value().startswith("sqrt 2 = "))

    def test_sqrt_then_binary(self):
        e = press_sequence(CalculatorEngine(), "9r+1=")
        self.assertEqual(e.display_value(), "4")
        self.assertEqual(e.formula_value(), "3 + 1 = 4")

    def test_sqrt_of_pending_entry(self):
        e = press_sequence(CalculatorEngine(), "2+9r=")
        self.assertEqual(e.display_value(), "5")
        self.assertEqual(e.formula_value(), "2 + 3 = 5")

    def test_sqrt_after_equals(self):
        e = press_sequence(CalculatorEngine(), "2+2=r")
        self.assertEqual(e.display_value(), "2")
        self.assertEqual(e.formula_value(), "sqrt 4 = 2")

    def test_sqrt_negative(self):
        e = press_sequence(CalculatorEngine(), "5-8=r")
        self.assertEqual(e.display_value(), u"Ошибка: корень из отрицательного числа")
        self.assertEqual(e.formula_value(), "")
        e.press_digit("7")
        self.assertEqual(e.display_value(), "7")

    def test_sqrt_with_nothing_entered(self):
        e = CalculatorEngine()
        e.press_operator("sqrt")
        self.assertEqual(e.display_value(), "0")
        self.assertEqual(e.formula_value(), "")


if __name__ == "__main__":
    unittest.main()
