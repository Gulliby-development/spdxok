from collections.abc import Iterator
from dataclasses import dataclass

from spdxok.expr import ExprError, Expression, parse_expression


@dataclass(frozen=True, slots=True)
class Package:
    name: str
    expression: Expression


class ListError(ValueError):
    """A package-list syntax error with its displayed location."""


def _physical_lines(text: str) -> Iterator[str]:
    text = text.removeprefix("\ufeff")
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if index < len(lines) - 1 and line.endswith("\r"):
            line = line[:-1]
        yield line


def parse_list(display: str, text: str) -> list[Package]:
    packages: list[Package] = []
    for line_number, physical_line in enumerate(_physical_lines(text), start=1):
        line = physical_line.strip(" \t")
        if not line or line.startswith("#"):
            continue

        separator = next((index for index, char in enumerate(line) if char in " \t"), None)
        if separator is None:
            raise ListError(f"{display}:{line_number}: expected NAME EXPRESSION")

        name = line[:separator]
        expression_text = line[separator:].strip(" \t")
        if not expression_text:
            raise ListError(f"{display}:{line_number}: expected NAME EXPRESSION")

        try:
            expression = parse_expression(expression_text)
        except ExprError as error:
            raise ListError(f"{display}:{line_number}: invalid expression: {error}") from error
        packages.append(Package(name, expression))
    return packages
