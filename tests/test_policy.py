import io

import pytest

from spdxok.cli import main
from spdxok.expr import ExprError, Leaf
from spdxok.policy import Policy, parse_entry


def _policy(allow=(), deny=()):
    return Policy(
        allow={parse_entry(entry) for entry in allow},
        deny={parse_entry(entry) for entry in deny},
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("MIT", Leaf("MIT")),
        ("Apache-2.0", Leaf("Apache-2.0")),
        ("GPL-3.0+", Leaf("GPL-3.0+")),
        ("LicenseRef-acme", Leaf("LicenseRef-acme")),
        ("mit", Leaf("mit")),
        ("MIT WITH Classpath-exception-2.0", Leaf("MIT", "Classpath-exception-2.0")),
        (
            "  MIT WITH Classpath-exception-2.0 \t",
            Leaf("MIT", "Classpath-exception-2.0"),
        ),
        ("mit\tWITH\tclasspath-exception-2.0", Leaf("mit", "classpath-exception-2.0")),
    ],
)
def test_parse_entry_accepts_one_license_with_optional_exception(text, expected):
    assert parse_entry(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "A OR B",
        "A AND B",
        "A WITH X OR B",
        "(A AND B)",
    ],
)
def test_parse_entry_rejects_compound_expressions(text):
    with pytest.raises(ExprError, match="expected one license entry"):
        parse_entry(text)


def test_parse_entry_rejects_parenthesized_single_license():
    with pytest.raises(ExprError, match="expected one license entry"):
        parse_entry("(MIT)")


@pytest.mark.parametrize(
    ("candidate", "allow", "deny", "expected"),
    [
        ("MIT", (), (), None),
        ("MIT", (), ("MIT",), "denied"),
        ("BSD-3-Clause", (), ("MIT",), None),
        ("MIT", ("MIT",), (), None),
        ("mit", ("MIT",), (), None),
        ("MIT", ("mit",), (), None),
        ("BSD-3-Clause", ("MIT",), (), "not allowed"),
        ("MIT WITH Classpath", ("MIT",), (), None),
        ("MIT WITH Classpath", ("MIT WITH Classpath",), (), None),
        ("mit WITH classpath", ("MIT WITH CLASSPATH",), (), None),
        ("MIT", ("MIT WITH Classpath",), (), "not allowed"),
        ("MIT WITH Other", ("MIT WITH Classpath",), (), "not allowed"),
        ("MIT WITH Classpath", (), ("MIT",), "denied"),
        ("mit WITH classpath", (), ("MIT WITH CLASSPATH",), "denied"),
        ("MIT", (), ("MIT WITH Classpath",), None),
        ("MIT WITH Other", (), ("MIT WITH Classpath",), None),
        ("MIT WITH Classpath", ("MIT",), ("MIT WITH Classpath",), "denied"),
        ("MIT", ("MIT",), ("mit",), "denied"),
        ("GPL-3.0+", ("GPL-3.0",), (), "not allowed"),
        ("GPL-3.0", ("GPL-3.0+",), (), "not allowed"),
        ("GPL-3.0+", (), ("GPL-3.0",), None),
    ],
)
def test_policy_reason_matches_allow_deny_and_exception_rules(candidate, allow, deny, expected):
    assert _policy(allow, deny).reason(parse_entry(candidate)) == expected


def test_policy_default_sets_are_independent():
    first = Policy()
    second = Policy()

    first.allow.add(Leaf("MIT"))

    assert first.reason(Leaf("MIT")) is None
    assert second.reason(Leaf("MIT")) is None
    assert second.allow == set()


def test_exception_permission_does_not_mutate_policy_entries():
    allowed = parse_entry("MIT")
    exception = parse_entry("MIT WITH Classpath")
    policy = Policy(allow={allowed})

    assert policy.reason(exception) is None
    assert policy.allow == {allowed}


def test_allow_file_reads_bom_crlf_and_single_license_entries(tmp_path):
    allow_file = tmp_path / "allow.txt"
    allow_file.write_bytes(
        b"\xef\xbb\xbf# allowed\r\nMIT\r\nMIT WITH Classpath\r\n"
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    status = main(
        ["check", "--allow-file", str(allow_file), "-"],
        stdin=io.BytesIO(b"plain MIT\r\nexception MIT WITH Classpath\r\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert status == 0
    assert stdout.getvalue() == "ok, 2 packages\n"
    assert stderr.getvalue() == ""


def test_allow_file_rejects_a_compound_entry_at_its_physical_line(tmp_path):
    allow_file = tmp_path / "allow.txt"
    allow_file.write_bytes(b"# allowed\r\nMIT\r\nA OR B\r\n")
    stdout = io.StringIO()
    stderr = io.StringIO()

    status = main(
        ["eval", "--allow-file", str(allow_file), "MIT"],
        stdout=stdout,
        stderr=stderr,
    )

    display_path = str(allow_file).replace("\\", "/")
    assert status == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == f'spdxok: {display_path}:3: invalid license "A OR B"\n'
