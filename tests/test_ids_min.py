import io

import pytest

from spdxok.cli import main

SEVEN = """# dependency licenses
left-pad MIT
express (MIT OR GPL-3.0)
lodash MIT AND (ISC OR BSD-3-Clause)
libfoo GPL-2.0 WITH Classpath-exception-2.0
zlib-ng Zlib
readline GPL-3.0+ OR AGPL-3.0
tool Apache-2.0 AND GPL-3.0
"""

ELEVEN = """a1 MIT
a2 MIT
a3 MIT
a4 MIT
a5 MIT
a6 MIT
a7 MIT
a8 MIT
a9 MIT
a10 MIT
b1 ISC
"""


def _run(arguments, tmp_path, text):
    list_file = tmp_path / "deps.txt"
    list_file.write_text(text, encoding="utf-8")
    stdout = io.StringIO()
    stderr = io.StringIO()
    status = main(
        [str(list_file) if argument == "LIST" else argument for argument in arguments],
        stdin=io.BytesIO(b""),
        stdout=stdout,
        stderr=stderr,
    )
    return status, stdout.getvalue(), stderr.getvalue()


@pytest.mark.parametrize(
    ("arguments", "text", "expected"),
    [
        (
            ["ids", "--min", "2", "LIST"],
            SEVEN,
            "3  MIT\n2  GPL-3.0\n2 of 9 distinct licenses in 7 packages\n",
        ),
        (
            ["ids", "--min=3", "LIST"],
            SEVEN,
            "3  MIT\n1 of 9 distinct licenses in 7 packages\n",
        ),
        (
            ["ids", "--min", "4", "LIST"],
            SEVEN,
            "0 of 9 distinct licenses in 7 packages\n",
        ),
        (
            ["ids", "--min", "1", "LIST"],
            SEVEN,
            (
                "3  MIT\n2  GPL-3.0\n1  AGPL-3.0\n1  Apache-2.0\n1  BSD-3-Clause\n"
                "1  GPL-2.0 WITH Classpath-exception-2.0\n1  GPL-3.0+\n1  ISC\n1  Zlib\n"
                "9 distinct licenses in 7 packages\n"
            ),
        ),
        (
            ["ids", "--min", "3", "--min", "2", "LIST"],
            SEVEN,
            "3  MIT\n2  GPL-3.0\n2 of 9 distinct licenses in 7 packages\n",
        ),
        (
            ["ids", "LIST", "--min", "007"],
            SEVEN,
            "0 of 9 distinct licenses in 7 packages\n",
        ),
        (
            ["ids", "--min", "2", "LIST"],
            ELEVEN,
            "10  MIT\n1 of 2 distinct licenses in 11 packages\n",
        ),
        (
            ["ids", "LIST"],
            ELEVEN,
            "10  MIT\n 1  ISC\n2 distinct licenses in 11 packages\n",
        ),
        (
            ["ids", "--min", "2", "LIST"],
            "solo MIT\n",
            "0 of 1 distinct license in 1 package\n",
        ),
        (
            ["ids", "--min", "2", "LIST"],
            "",
            "0 distinct licenses in 0 packages\n",
        ),
    ],
)
def test_ids_min_lists_only_licenses_used_by_enough_packages(tmp_path, arguments, text, expected):
    assert _run(arguments, tmp_path, text) == (0, expected, "")


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["ids", "--min", "0", "LIST"], 'invalid --min "0"'),
        (["ids", "--min", "000", "LIST"], 'invalid --min "000"'),
        (["ids", "--min=abc", "LIST"], 'invalid --min "abc"'),
        (["ids", "--min", "1.5", "LIST"], 'invalid --min "1.5"'),
        (["ids", "--min", "-1", "LIST"], 'invalid --min "-1"'),
        (["ids", "--min", "", "LIST"], 'invalid --min ""'),
        (["ids", "--min=", "LIST"], 'invalid --min ""'),
        (["ids", "--min", "1234567890", "LIST"], 'invalid --min "1234567890"'),
        (
            ["ids", "--min", "\N{ARABIC-INDIC DIGIT THREE}", "LIST"],
            'invalid --min "\N{ARABIC-INDIC DIGIT THREE}"',
        ),
        (["ids", "LIST", "--min"], "--min needs a value"),
        (["ids", "--min", "x", "missing.txt"], 'invalid --min "x"'),
        (["ids", "--min", "2"], "missing LIST"),
        (["check", "--allow", "MIT", "--min", "2", "LIST"], 'unknown option "--min"'),
        (["eval", "--allow", "MIT", "--min=2", "MIT"], 'unknown option "--min=2"'),
    ],
)
def test_ids_min_errors(tmp_path, arguments, message):
    assert _run(arguments, tmp_path, SEVEN) == (2, "", f"spdxok: {message}\n")
