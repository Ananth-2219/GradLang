"""Convert source text into positioned tokens and explicit indentation tokens."""

from dataclasses import dataclass
import re
from typing import List


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


class LexerError(SyntaxError):
    """An illegal character or invalid indentation in source text."""


NUMBER = re.compile(r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
KEYWORDS = {"fn": "FN", "return": "RETURN"}
SYMBOLS = set("+-*/^()=:,")


def tokenize(source: str) -> List[Token]:
    """Return tokens ending in EOF. Positions are one-based character offsets."""
    tokens = []
    indent_levels = [0]
    # Normalize platform line endings; only physical lines delimit statements.
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    for line_number, line in enumerate(lines, start=1):
        if "\t" in line:
            column = line.index("\t") + 1
            raise LexerError(f"Tabs are not allowed at line {line_number}, column {column}")
        if not line.strip(" "):
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent > indent_levels[-1]:
            indent_levels.append(indent)
            tokens.append(Token("INDENT", "", line_number, indent + 1))
        elif indent < indent_levels[-1]:
            if indent not in indent_levels:
                raise LexerError(
                    f"Inconsistent indentation at line {line_number}, column {indent + 1}"
                )
            while indent < indent_levels[-1]:
                indent_levels.pop()
                tokens.append(Token("DEDENT", "", line_number, indent + 1))

        position = indent
        while position < len(line):
            character = line[position]
            if character == " ":
                position += 1
                continue

            match = NUMBER.match(line, position)
            if match:
                kind = "NUMBER"
                value = match.group()
            else:
                match = IDENTIFIER.match(line, position)
                if match:
                    value = match.group()
                    kind = KEYWORDS.get(value, "IDENT")
                elif character in SYMBOLS:
                    kind = value = character
                else:
                    raise LexerError(
                        f"Illegal character {character!r} at line {line_number}, "
                        f"column {position + 1}"
                    )
            tokens.append(Token(kind, value, line_number, position + 1))
            position += len(value)

        # Also terminate a final source line without a trailing newline.
        tokens.append(Token("NEWLINE", "", line_number, len(line) + 1))

    eof_line, eof_column = len(lines), len(lines[-1]) + 1
    while len(indent_levels) > 1:
        indent_levels.pop()
        tokens.append(Token("DEDENT", "", eof_line, eof_column))
    tokens.append(Token("EOF", "", eof_line, eof_column))
    return tokens
