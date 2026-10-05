"""Core arithmetic operations."""

from __future__ import division


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


def multiply(a, b):
    return a * b


def divide(a, b):
    if b == 0:
        raise ZeroDivisionError("division by zero")
    return a / b


def pow(a, b):
    if a < 0 and b != int(b):
        raise ValueError("negative base with a fractional exponent")
    return a ** b


def sqrt(a):
    if a < 0:
        raise ValueError("square root of a negative number")
    return a ** 0.5


OPERATORS = {
    "+": add,
    "-": subtract,
    "*": multiply,
    "/": divide,
    "pow": pow,
}

UNARY_OPERATORS = {
    "sqrt": sqrt,
}


def _parse(token, expression):
    try:
        return float(token)
    except ValueError:
        raise ValueError("could not parse a number in %r" % expression)


def calculate(expression):
    """Evaluate a 'a op b' expression such as '3 + 4', or a unary
    expression like '9 sqrt'.

    Returns an int when the result is a whole number, a float otherwise.
    Raises ValueError for malformed input and ZeroDivisionError on x / 0.
    """
    tokens = expression.split()
    if len(tokens) == 3:
        left, op, right = tokens
        if op not in OPERATORS:
            raise ValueError("unknown operator %r (supported: + - * / pow)" % op)
        result = OPERATORS[op](_parse(left, expression),
                               _parse(right, expression))
    elif len(tokens) == 2:
        first, second = tokens
        if first in UNARY_OPERATORS:
            op, arg = first, second
        elif second in UNARY_OPERATORS:
            op, arg = second, first
        else:
            raise ValueError(
                "expected an expression like '3 + 4' or '9 sqrt', got %r"
                % expression)
        result = UNARY_OPERATORS[op](_parse(arg, expression))
    else:
        raise ValueError(
            "expected an expression like '3 + 4' or '9 sqrt', got %r"
            % expression)
    return int(result) if result.is_integer() else result
