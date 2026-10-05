"""Interactive command line interface."""

from __future__ import print_function

try:
    raw_input
except NameError:
    raw_input = input

from .core import calculate

PROMPT = ">>> "
HELP = "Enter an expression like '3 + 4' or '9 sqrt' (operators: + - * / pow sqrt). Type 'quit' to exit."


def main():
    print("Simple calculator")
    print(HELP)
    while True:
        try:
            line = raw_input(PROMPT).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line.lower() in ("quit", "exit", "q"):
            break
        try:
            print(calculate(line))
        except ZeroDivisionError:
            print("Error: division by zero")
        except ValueError as exc:
            print("Error: %s" % exc)


if __name__ == "__main__":
    main()
