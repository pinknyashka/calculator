# -*- coding: utf-8 -*-
"""Pure state machine driving the calculator. No GUI dependencies."""

from .core import calculate, sqrt


class CalculatorEngine(object):
    MAX_DIGITS = 15

    def __init__(self):
        self.reset()

    def reset(self):
        self.operand = None
        self.operator = None
        self.entry = ""
        self.result_formula = None
        self.error = None

    # --- input handlers ---

    def press_digit(self, digit):
        if self.error is not None:
            self.reset()
        if self.result_formula is not None:
            self.reset()
        if len(self.entry.replace(".", "", 1)) >= self.MAX_DIGITS:
            return
        self.entry += digit

    def press_dot(self):
        if self.error is not None:
            self.reset()
        if self.result_formula is not None:
            self.reset()
        if "." in self.entry:
            return
        self.entry = (self.entry if self.entry else "0") + "."

    def press_operator(self, op):
        if self.error is not None:
            self.reset()
        if op == "sqrt":
            self._apply_sqrt()
            return
        if self.result_formula is not None:
            self.result_formula = None
        if self.entry:
            if self.operand is None:
                self.operand = self._value()
            else:
                self.operand = calculate(
                    "%s %s %s" % (self._fmt(self.operand), self.operator,
                                  self._fmt(self._value())))
            self.entry = ""
        elif self.operand is None and self.operator is None:
            return
        self.operator = op

    def _apply_sqrt(self):
        if self.entry:
            value = self._value()
        elif self.operand is not None:
            value = self.operand
        else:
            return
        try:
            result = sqrt(value)
        except ValueError:
            self.error = u"Ошибка: корень из отрицательного числа"
            self.operand = None
            self.operator = None
            self.entry = ""
            return
        if self.operator is None:
            self.result_formula = "sqrt %s = %s" % (self._fmt(value),
                                                     self._fmt(result))
            self.operand = result
            self.entry = ""
        else:
            self.entry = self._fmt(result)

    def press_equals(self):
        if self.error is not None:
            self.reset()
            return
        if self.operand is None or self.operator is None or not self.entry:
            return
        formula = "%s %s %s" % (self._fmt(self.operand), self.operator, self._fmt(self._value()))
        try:
            result = calculate(formula)
        except ZeroDivisionError:
            self.error = u"Ошибка: деление на ноль"
            self.operand = None
            self.operator = None
            self.entry = ""
            return
        except ValueError:
            self.error = u"Ошибка: отрицательное основание"
            self.operand = None
            self.operator = None
            self.entry = ""
            return
        self.result_formula = "%s = %s" % (formula, self._fmt(result))
        self.operand = result
        self.operator = None
        self.entry = ""

    def press_backspace(self):
        if self.error is not None:
            self.reset()
            return
        if self.result_formula is not None:
            return
        self.entry = self.entry[:-1]

    def press_clear(self):
        self.reset()

    # --- display helpers ---

    def display_value(self):
        if self.error is not None:
            return self.error
        if self.result_formula is not None:
            return self._fmt(self.operand)
        return self.entry if self.entry else "0"

    def formula_value(self):
        if self.error is not None or self.operand is None:
            return ""
        if self.result_formula is not None:
            return self.result_formula
        if self.operator is not None:
            return "%s %s" % (self._fmt(self.operand), self.operator)
        return ""

    # --- internals ---

    def _value(self):
        value = float(self.entry)
        return int(value) if value.is_integer() else value

    @staticmethod
    def _fmt(value):
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return str(value)
