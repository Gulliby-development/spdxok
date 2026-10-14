import io

import pytest

from spdxok.cli import main
from spdxok.expr import And, ExprError, Leaf, Or, leaves, parse_expression


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT", Leaf("MIT")),
        ("Apache-2.0", Leaf("Apache-2.0")),
        ("GPL-3.0+", Leaf("GPL-3.0+")),
        ("LicenseRef-acme", Leaf("LicenseRef-acme")),
        ("0BSD", Leaf("0BSD")),
        ("A.B-C", Leaf("A.B-C")),
        ("mit", Leaf("mit")),
        ("GPL-3.0", Leaf("GPL-3.0")),
    ],
)
def test_identifier_forms_are_preserved(text, expected):
    assert parse_expression(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "A AND B AND C",
            And((Leaf("A"), Leaf("B"), Leaf("C"))),
        ),
        (
            "A OR B OR C",
            Or((Leaf("A"), Leaf("B"), Leaf("C"))),
        ),
        (
            "A AND B OR C AND D",
            Or((And((Leaf("A"), Leaf("B"))), And((Leaf("C"), Leaf("D"))))),
        ),
        (
            "A OR B AND C",
            Or((Leaf("A"), And((Leaf("B"), Leaf("C"))))),
        ),
        (
            "(A OR B) AND C",
            And((Or((Leaf("A"), Leaf("B"))), Leaf("C"))),
        ),
        (
            "A AND (B AND C)",
            And((Leaf("A"), And((Leaf("B"), Leaf("C"))))),
        ),
        (
            "A OR (B AND (C OR D))",
            Or((Leaf("A"), And((Leaf("B"), Or((Leaf("C"), Leaf("D"))))))),
        ),
        ("((MIT))", Leaf("MIT")),
    ],
)
def test_operators_and_parentheses_build_the_expected_tree(text, expected):
    assert parse_expression(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT\tAND\tApache-2.0", And((Leaf("MIT"), Leaf("Apache-2.0")))),
        ("\t(MIT OR BSD)\t", Or((Leaf("MIT"), Leaf("BSD")))),
        ("  MIT  ", Leaf("MIT")),
        ("MIT WITH Classpath-exception-2.0", Leaf("MIT", "Classpath-exception-2.0")),
        ("mit WITH classpath-exception-2.0", Leaf("mit", "classpath-exception-2.0")),
        ("GPL-3.0+ OR GPL-3.0", Or((Leaf("GPL-3.0+"), Leaf("GPL-3.0")))),
        ("or", Leaf("or")),
    ],
)
def test_optional_whitespace_exceptions_and_operator_case(text, expected):
    assert parse_expression(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT AND (BSD OR GPL-3.0)", [Leaf("MIT"), Leaf("BSD"), Leaf("GPL-3.0")]),
        ("GPL-3.0+ OR GPL-3.0", [Leaf("GPL-3.0+"), Leaf("GPL-3.0")]),
        (
            "MIT WITH Classpath-exception-2.0 OR Apache-2.0",
            [Leaf("MIT", "Classpath-exception-2.0"), Leaf("Apache-2.0")],
        ),
        ("((MIT))", [Leaf("MIT")]),
    ],
)
def test_leaves_returns_left_to_right_license_leaves(text, expected):
    assert leaves(parse_expression(text)) == expected


@pytest.mark.parametrize(
    ("text", "message", "column"),
    [
        ("", "empty expression", 1),
        (" \t ", "empty expression", 1),
        (" \t@\t ", 'unexpected character "@"', 1),
        ("-MIT", 'unexpected character "-"', 1),
        (" \t-MIT\t ", 'unexpected character "-"', 1),
        ("MIT_1", 'unexpected character "_"', 4),
        ("é", 'unexpected character "é"', 1),
        ("MIT:BSD", 'unexpected character ":"', 4),
        ("MIT++", 'unexpected character "+"', 5),
        ("AND MIT", 'expected a license, found "AND"', 1),
        ("MIT OR", "expected a license, found end of expression", 7),
        ("MIT AND )", 'expected a license, found ")"', 9),
        ("MIT OR WITH X", 'expected a license, found "WITH"', 8),
        ("()", 'expected a license, found ")"', 2),
        ("(OR A)", 'expected a license, found "OR"', 2),
        ("MIT WITH", "expected an exception, found end of expression", 9),
        ("MIT WITH AND BSD", 'expected an exception, found "AND"', 10),
        ("MIT WITH OR", 'expected an exception, found "OR"', 10),
        ("MIT WITH WITH", 'expected an exception, found "WITH"', 10),
        ("MIT WITH (BSD)", 'expected an exception, found "("', 10),
        ("MIT WITH )", 'expected an exception, found ")"', 10),
        ("MIT BSD", 'unexpected "BSD"', 5),
        ("MIT (BSD)", 'unexpected "("', 5),
        ("MIT WITH X WITH Y", 'unexpected "WITH"', 12),
        ("(MIT) WITH Classpath", 'unexpected "WITH"', 7),
        (")", 'expected a license, found ")"', 1),
        ("MIT )", 'unmatched ")"', 5),
        ("(MIT", 'missing ")"', 1),
        ("(MIT AND (BSD", 'missing ")"', 10),
        ("((MIT)", 'missing ")"', 1),
        ("(MIT AND ((BSD", 'missing ")"', 11),
        ("(MIT) OR (BSD", 'missing ")"', 10),
        ("MIT AND GPL)", 'unmatched ")"', 12),
        ("MIT AND OR", 'expected a license, found "OR"', 9),
        ("MIT AND (BSD OR )", 'expected a license, found ")"', 17),
        ("MIT WITH X OR", "expected a license, found end of expression", 14),
        (" \t MIT OR\t ", "expected a license, found end of expression", 7),
        (" \t MIT AND ) \t ", 'expected a license, found ")"', 9),
    ],
)
def test_expression_errors_have_exact_messages_and_trimmed_columns(text, message, column):
    with pytest.raises(ExprError) as error:
        parse_expression(text)

    assert error.value.message == message
    assert error.value.column == column
    assert str(error.value) == f"{message} (column {column})"


def test_deeply_nested_expression_works_through_cli():
    expression = "(" * 350 + "MIT" + ")" * 350
    stdout = io.StringIO()
    stderr = io.StringIO()

    status = main(
        ["eval", "--allow", "MIT", expression],
        stdin=io.BytesIO(),
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 0
    assert stdout.getvalue() == "ok: uses MIT\n"
    assert stderr.getvalue() == ""