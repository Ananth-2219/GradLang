"""Run with: python tests/demo_phase1.py (from the project root)."""

from pathlib import Path
from pprint import pprint
import sys

# Direct script execution puts tests/, rather than the project root, on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gradlang.lexer import tokenize
from gradlang.parser import ParseError, Parser


SAMPLE = """fn loss(x, w, b):
    y = w * x + b
    return (y - 1) ^ 2
"""


def main():
    print("Sample source:")
    print(SAMPLE)
    print("Abstract syntax tree:")
    pprint(Parser(tokenize(SAMPLE)).parse(), width=72)

    malformed = "fn loss(x):\n    return (x + )\n"
    print("\nDeliberately malformed input:")
    print(malformed)
    try:
        Parser(tokenize(malformed)).parse()
    except ParseError as error:
        print(f"Syntax error: {error}")
    else:
        raise AssertionError("Malformed input was unexpectedly accepted")


if __name__ == "__main__":
    main()
