import re
from pathlib import Path

README_PATH = Path(__file__).resolve().parents[1] / "README.md"

USAGE_LINES = """usage: spdxok eval [--allow IDS]... [--allow-file FILE]... [--deny IDS]... EXPRESSION
       spdxok check [--allow IDS]... [--allow-file FILE]... [--deny IDS]... [--all] LIST
       spdxok ids [--min COUNT] LIST"""

DEPENDENCIES = """# dependency licenses
left-pad MIT
express (MIT OR GPL-3.0)
lodash MIT AND (ISC OR BSD-3-Clause)
libfoo GPL-2.0 WITH Classpath-exception-2.0
zlib-ng Zlib
readline GPL-3.0+ OR AGPL-3.0
tool Apache-2.0 AND GPL-3.0"""

CHECK_OUTPUT = """libfoo: blocked: GPL-2.0 WITH Classpath-exception-2.0 (not allowed)
readline: blocked: GPL-3.0+ (not allowed), AGPL-3.0 (denied)
tool: blocked: GPL-3.0 (not allowed)
3 of 7 packages blocked"""

IDS_OUTPUT = """3  MIT
2  GPL-3.0
1  AGPL-3.0
1  Apache-2.0
1  BSD-3-Clause
1  GPL-2.0 WITH Classpath-exception-2.0
1  GPL-3.0+
1  ISC
1  Zlib
9 distinct licenses in 7 packages"""


def _readme():
    return README_PATH.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


def test_readme_has_required_headings():
    readme = _readme()

    for heading in (
        "## Install",
        "## Usage",
        "## Expressions",
        "## Policy",
        "## Exit codes",
        "## Development",
    ):
        assert f"\n{heading}\n" in readme


def test_readme_contains_the_exact_usage_and_dependency_list_blocks():
    readme = _readme()
    expected_blocks = (
        f"\x60\x60\x60text\n{USAGE_LINES}\n\x60\x60\x60",
        f"\x60\x60\x60text\n{DEPENDENCIES}\n\x60\x60\x60",
    )

    for block in expected_blocks:
        assert readme.count(block) == 1


def test_readme_contains_the_exact_check_and_ids_output_blocks():
    readme = _readme()
    expected_blocks = (
        f"\x60\x60\x60text\n{CHECK_OUTPUT}\n\x60\x60\x60",
        f"\x60\x60\x60text\n{IDS_OUTPUT}\n\x60\x60\x60",
    )

    for block in expected_blocks:
        assert readme.count(block) == 1


def test_readme_has_no_additional_text_example_blocks():
    readme = _readme()
    actual_blocks = re.findall(r"\x60\x60\x60text\n(.*?)\n\x60\x60\x60", readme, re.DOTALL)

    assert actual_blocks == [USAGE_LINES, DEPENDENCIES, CHECK_OUTPUT, IDS_OUTPUT]
