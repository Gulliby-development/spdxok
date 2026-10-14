import pytest

from spdxok.expr import And, Leaf, Or
from spdxok.listing import ListError, Package, parse_list


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("\ufeff", []),
        ("# dependency licenses\n\n \t\n", []),
    ],
)
def test_empty_and_comment_only_lists_have_no_packages(text, expected):
    assert parse_list("deps.txt", text) == expected


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_bom_comments_and_physical_lines_are_parsed(newline):
    text = newline.join(
        [
            "\ufeff# dependency licenses",
            "",
            "  # a comment after indentation",
            "left-pad MIT",
            "express (MIT OR GPL-3.0)",
            "",
        ]
    )

    packages = parse_list("deps.txt", text)

    assert packages == [
        Package("left-pad", Leaf("MIT")),
        Package("express", Or((Leaf("MIT"), Leaf("GPL-3.0")))),
    ]


def test_list_splits_name_at_first_space_or_tab_and_trims_expression():
    packages = parse_list(
        "deps.txt",
        "  @odd-name\t  MIT\tAND (ISC OR BSD-3-Clause)  \n"
        "tool   GPL-3.0+  ",
    )

    assert packages == [
        Package("@odd-name", And((Leaf("MIT"), Or((Leaf("ISC"), Leaf("BSD-3-Clause")))))),
        Package("tool", Leaf("GPL-3.0+")),
    ]


def test_package_order_is_preserved():
    assert parse_list("deps.txt", "z-last MIT\na-first BSD\nmiddle ISC") == [
        Package("z-last", Leaf("MIT")),
        Package("a-first", Leaf("BSD")),
        Package("middle", Leaf("ISC")),
    ]


@pytest.mark.parametrize(
    ("text", "line_number"),
    [
        ("package\n", 1),
        ("\n# comment\npackage \t \n", 3),
    ],
)
def test_missing_expression_reports_physical_line_number(text, line_number):
    with pytest.raises(ListError) as error:
        parse_list("deps.txt", text)

    assert str(error.value) == f"deps.txt:{line_number}: expected NAME EXPRESSION"


def test_missing_name_separator_reports_expected_record_shape():
    with pytest.raises(ListError) as error:
        parse_list("lists/deps.txt", "# first line\n\npackage")

    assert str(error.value) == "lists/deps.txt:3: expected NAME EXPRESSION"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("pkg @MIT", 'deps.txt:1: invalid expression: unexpected character "@" (column 1)'),
        (
            "pkg MIT OR",
            (
                  "deps.txt:1: invalid expression: expected a license, found end of expression "
                  "(column 7)"
            ),
        ),
        (
            "\n# comment\n pkg MIT AND )",
            'deps.txt:3: invalid expression: expected a license, found ")" (column 9)',
        ),
    ],
)
def test_invalid_expression_reports_display_and_exact_parser_error(text, expected):
    with pytest.raises(ListError) as error:
        parse_list("deps.txt", text)

    assert str(error.value) == expected


def test_only_one_initial_bom_is_removed():
    with pytest.raises(ListError) as error:
        parse_list("deps.txt", "\ufeffpkg MIT\npkg \ufeffMIT")

    assert str(error.value) == (
        'deps.txt:2: invalid expression: unexpected character "\ufeff" (column 1)'
    )


def test_carriage_return_is_removed_only_before_a_line_feed():
    with pytest.raises(ListError) as error:
        parse_list("deps.txt", "pkg MIT\r")

    assert str(error.value) == (
        'deps.txt:1: invalid expression: unexpected character "\r" (column 4)'
    )


def test_hash_after_a_package_name_is_not_a_comment_line():
    with pytest.raises(ListError) as error:
        parse_list("deps.txt", "pkg # not a full-line comment")

    assert str(error.value) == (
        'deps.txt:1: invalid expression: unexpected character "#" (column 1)'
    )
