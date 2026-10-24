import io
from pathlib import Path

import pytest

from spdxok.cli import main

HELP = (
    "usage: spdxok eval [--allow IDS]... [--allow-file FILE]... [--deny IDS]... EXPRESSION\n"
    "       spdxok check [--allow IDS]... [--allow-file FILE]... [--deny IDS]... [--all] LIST\n"
    "       spdxok ids [--min COUNT] LIST\n"
)


def _run(arguments, input_bytes=b""):
    stdout = io.StringIO()
    stderr = io.StringIO()
    status = main(
        arguments,
        stdin=io.BytesIO(input_bytes),
        stdout=stdout,
        stderr=stderr,
    )
    return status, stdout.getvalue(), stderr.getvalue()


def _display(path: Path) -> str:
    return str(path).replace("\\", "/")


def _error(message):
    return 2, "", f"spdxok: {message}\n"


def test_help_is_printed_only_when_it_is_the_only_argument():
    assert _run(["--help"]) == (0, HELP, "")


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ([], "missing command (eval, check or ids)"),
        (["install"], 'unknown command "install"'),
        (["--help", "eval"], 'unknown option "--help"'),
        (["eval", "--help"], 'unknown option "--help"'),
        (["check", "deps.txt", "--help"], 'unknown option "--help"'),
        (["ids", "--help"], 'unknown option "--help"'),
    ],
)
def test_command_and_help_argument_errors(arguments, message):
    assert _run(arguments) == _error(message)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["eval", "--allow"], "--allow needs a value"),
        (["eval", "--allow-file"], "--allow-file needs a value"),
        (["check", "--deny"], "--deny needs a value"),
        (["eval", "--allow", "--help", "MIT"], 'unknown option "--help"'),
        (["eval", "--deny", "--help", "MIT"], 'unknown option "--help"'),
        (["check", "deps.txt", "--allow-file", "--help"], 'unknown option "--help"'),
        (["eval", "--allow=A OR B", "MIT"], 'invalid license "A OR B" in --allow'),
        (["check", "--deny=A AND B", "deps.txt"], 'invalid license "A AND B" in --deny'),
        (["eval", "--allow=", "MIT"], 'invalid license "" in --allow'),
        (["eval", "--unknown", "MIT"], 'unknown option "--unknown"'),
        (["eval", "-expression"], 'unknown option "-expression"'),
        (["eval", "MIT", "BSD"], "too many arguments"),
        (["check", "one.txt", "two.txt"], "too many arguments"),
        (["eval"], "missing EXPRESSION"),
        (["check"], "missing LIST"),
        (["ids"], "missing LIST"),
        (
            ["eval", "MIT"],
            "no policy given (use --allow, --allow-file or --deny)",
        ),
        (
            ["check", "deps.txt"],
            "no policy given (use --allow, --allow-file or --deny)",
        ),
        (["ids", "--allow", "MIT", "deps.txt"], 'unknown option "--allow"'),
        (["ids", "--deny=MIT", "deps.txt"], 'unknown option "--deny=MIT"'),
        (
            ["ids", "--allow-file", "allow.txt", "deps.txt"],
            'unknown option "--allow-file"',
        ),
    ],
)
def test_argument_errors_have_exact_prefix_stream_and_status(arguments, message):
    assert _run(arguments) == _error(message)


def test_option_equals_forms_and_options_after_the_positional_are_accepted():
    assert _run(["eval", "MIT", "--allow=MIT", "--deny=GPL-3.0"]) == (
        0,
        "ok: uses MIT\n",
        "",
    )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["eval", "--allow", "A OR B", "MIT"], 'invalid license "A OR B" in --allow'),
        (["eval", "--allow", "MIT", "--deny", "A OR B"], 'invalid license "A OR B" in --deny'),
        (["eval", "--allow", "MIT", "--bogus"], 'unknown option "--bogus"'),
        (["eval", "--allow", "MIT", "MIT", "extra"], "too many arguments"),
    ],
)
def test_arguments_stop_at_the_first_left_to_right_problem(arguments, message):
    assert _run(arguments) == _error(message)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["eval", "--allow-file", "missing.txt"], "missing EXPRESSION"),
        (["check", "--allow-file", "missing.txt"], "missing LIST"),
    ],
)
def test_required_positionals_are_checked_before_allow_files(arguments, message):
    assert _run(arguments) == _error(message)


def test_no_policy_is_checked_before_reading_a_list_or_expression():
    assert _run(["check", "missing.txt"]) == _error(
        "no policy given (use --allow, --allow-file or --deny)"
    )


@pytest.mark.parametrize(
    ("expression", "options", "expected"),
    [
        ("MIT OR GPL-3.0", ["--allow", "MIT"], "ok: uses MIT\n"),
        (
            "GPL-3.0 OR (AGPL-3.0 AND MIT)",
            ["--allow", "MIT"],
            "blocked: GPL-3.0 (not allowed), AGPL-3.0 (not allowed)\n",
        ),
        (
            "MIT OR GPL-3.0",
            ["--allow=MIT"],
            "ok: uses MIT\n",
        ),
    ],
)
def test_eval_success_and_blocked_output(expression, options, expected):
    status, stdout, stderr = _run(["eval", *options, expression])

    assert status == (0 if expected.startswith("ok:") else 1)
    assert stdout == expected
    assert stderr == ""


@pytest.mark.parametrize(
    ("expression", "diagnostic"),
    [
        ("", "empty expression (column 1)"),
        ("MIT or Apache-2.0", 'unexpected "or" (column 5)'),
        ("MIT OR", "expected a license, found end of expression (column 7)"),
        ("MIT WITH", "expected an exception, found end of expression (column 9)"),
        (" MIT OR  ", "expected a license, found end of expression (column 7)"),
    ],
)
def test_eval_reports_expression_errors_with_exact_trimmed_columns(expression, diagnostic):
    assert _run(["eval", "--allow", "MIT", expression]) == _error(
        f"invalid expression: {diagnostic}"
    )


def _write_dependencies(tmp_path):
    path = tmp_path / "deps.txt"
    path.write_text(
        "# dependency licenses\n"
        "left-pad MIT\n"
        "express (MIT OR GPL-3.0)\n"
        "lodash MIT AND (ISC OR BSD-3-Clause)\n"
        "libfoo GPL-2.0 WITH Classpath-exception-2.0\n"
        "zlib-ng Zlib\n"
        "readline GPL-3.0+ OR AGPL-3.0\n"
        "tool Apache-2.0 AND GPL-3.0\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


def test_check_prints_blocked_packages_in_input_order_with_exact_summary(tmp_path):
    dependencies = _write_dependencies(tmp_path)

    assert _run(
        [
            "check",
            "--allow",
            "MIT,ISC,Zlib",
            "--allow",
            "Apache-2.0",
            "--deny",
            "AGPL-3.0",
            str(dependencies),
        ]
    ) == (
        1,
        (
            "libfoo: blocked: GPL-2.0 WITH Classpath-exception-2.0 (not allowed)\n"
            "readline: blocked: GPL-3.0+ (not allowed), AGPL-3.0 (denied)\n"
            "tool: blocked: GPL-3.0 (not allowed)\n"
            "3 of 7 packages blocked\n"
        ),
        "",
    )


def test_check_and_ids_accept_the_list_from_standard_input():
    assert _run(
        ["check", "--allow=MIT", "-"],
        b"left MIT\nright BSD-3-Clause\n",
    ) == (
        1,
        "right: blocked: BSD-3-Clause (not allowed)\n1 of 2 packages blocked\n",
        "",
    )
    assert _run(["ids", "-"], b"left MIT\nright BSD-3-Clause\n") == (
        0,
        "1  BSD-3-Clause\n1  MIT\n2 distinct licenses in 2 packages\n",
        "",
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", "ok, 0 packages\n"),
        ("# no packages\n\n", "ok, 0 packages\n"),
        ("one MIT\n", "ok, 1 package\n"),
    ],
)
def test_check_success_summary_handles_empty_and_singular_lists(tmp_path, text, expected):
    dependencies = tmp_path / "deps.txt"
    dependencies.write_text(text, encoding="utf-8", newline="\n")

    assert _run(["check", "--deny", "GPL-3.0", str(dependencies)]) == (0, expected, "")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", "0 distinct licenses in 0 packages\n"),
        ("# no packages\n", "0 distinct licenses in 0 packages\n"),
        ("one MIT\n", "1  MIT\n1 distinct license in 1 package\n"),
    ],
)
def test_ids_summary_handles_empty_and_singular_lists(tmp_path, text, expected):
    dependencies = tmp_path / "deps.txt"
    dependencies.write_text(text, encoding="utf-8", newline="\n")

    assert _run(["ids", str(dependencies)]) == (0, expected, "")


def test_ids_counts_each_case_insensitive_license_once_per_package_and_sorts(tmp_path):
    dependencies = tmp_path / "deps.txt"
    dependencies.write_text(
        "first MIT AND mit AND BSD-3-Clause\n"
        "second BSD-3-Clause OR MIT\n"
        "third GPL-3.0+\n",
        encoding="utf-8",
        newline="\n",
    )

    assert _run(["ids", str(dependencies)]) == (
        0,
        (
            "2  BSD-3-Clause\n"
            "2  MIT\n"
            "1  GPL-3.0+\n"
            "3 distinct licenses in 3 packages\n"
        ),
        "",
    )


def test_check_allow_file_supports_bom_crlf_comments_and_exception_permission(tmp_path):
    allow_file = tmp_path / "allow.txt"
    allow_file.write_bytes(
        b"\xef\xbb\xbf# allowed\r\nMIT\r\n"
        b"GPL-2.0 WITH Classpath-exception-2.0\r\nzlib\r\n"
    )
    dependencies = tmp_path / "deps.txt"
    dependencies.write_bytes(
        b"plain MIT\r\n"
        b"exception GPL-2.0 WITH Classpath-exception-2.0\r\n"
        b"lower zlib\r\n"
    )

    assert _run(["check", "--allow-file", str(allow_file), str(dependencies)]) == (
        0,
        "ok, 3 packages\n",
        "",
    )


@pytest.mark.parametrize(
    ("payload", "line", "entry"),
    [
        (b"# allowed\nMIT\nA OR B\n", 3, "A OR B"),
        (b"\xef\xbb\xbfMIT\r\n\tA AND B\t\r\n", 2, "A AND B"),
    ],
)
def test_allow_file_invalid_entry_reports_normalized_path_and_physical_line(
    tmp_path, payload, line, entry
):
    allow_file = tmp_path / "allow.txt"
    allow_file.write_bytes(payload)

    assert _run(["eval", "--allow-file", str(allow_file), "MIT"]) == _error(
        f'{_display(allow_file)}:{line}: invalid license "{entry}"'
    )


@pytest.mark.parametrize(
    ("command", "path", "message"),
    [
        ("eval", "missing-allow.txt", "missing-allow.txt: cannot read the file"),
        ("check", "missing-deps.txt", "missing-deps.txt: cannot read the file"),
        ("ids", "missing-deps.txt", "missing-deps.txt: cannot read the file"),
    ],
)
def test_unreadable_files_are_reported_without_stdout(tmp_path, command, path, message):
    if command == "eval":
        arguments = [command, "--allow-file", str(tmp_path / path), "MIT"]
    elif command == "check":
        arguments = [command, "--deny", "GPL-3.0", str(tmp_path / path)]
    else:
        arguments = [command, str(tmp_path / path)]

    expected = message.replace(path, _display(tmp_path / path))
    assert _run(arguments) == _error(expected)


@pytest.mark.parametrize("command", ["check", "ids"])
def test_list_files_reject_invalid_utf8_with_normalized_path(tmp_path, command):
    dependencies = tmp_path / "bad.txt"
    dependencies.write_bytes(b"pkg MIT\n\xff\xfe")

    if command == "check":
        arguments = [command, "--deny", "GPL-3.0", str(dependencies)]
    else:
        arguments = [command, str(dependencies)]

    assert _run(arguments) == _error(f"{_display(dependencies)}: input is not valid UTF-8")


def test_allow_file_rejects_invalid_utf8_before_expression_evaluation(tmp_path):
    allow_file = tmp_path / "bad-allow.txt"
    allow_file.write_bytes(b"MIT\n\xff")

    assert _run(["eval", "--allow-file", str(allow_file), "not an expression"]) == _error(
        f"{_display(allow_file)}: input is not valid UTF-8"
    )


def test_list_parser_errors_include_normalized_path_physical_line_and_column(tmp_path):
    dependencies = tmp_path / "deps.txt"
    dependencies.write_bytes(b"# first\r\n\r\npackage MIT OR\r\n")

    assert _run(["ids", str(dependencies)]) == _error(
        f"{_display(dependencies)}:3: invalid expression: "
        "expected a license, found end of expression (column 7)"
    )


def test_dash_is_an_ordinary_allow_file_name_not_standard_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "-").write_text("MIT\n", encoding="utf-8", newline="\n")

    assert _run(["eval", "--allow-file", "-", "MIT"]) == (0, "ok: uses MIT\n", "")


class _UnreadableStream(io.BytesIO):
    def read(self, *args, **kwargs):
        raise OSError("stream read failed")


def test_stdin_read_failure_uses_the_stdin_display_name():
    stdout = io.StringIO()
    stderr = io.StringIO()

    status = main(
        ["ids", "-"],
        stdin=_UnreadableStream(),
        stdout=stdout,
        stderr=stderr,
    )

    assert (status, stdout.getvalue(), stderr.getvalue()) == _error(
        "<stdin>: cannot read the file"
    )


def test_check_all_mixed_report_matches_example_for_stdin_and_file(tmp_path):
    text = (
        "left-pad MIT\n"
        "express (MIT OR GPL-3.0)\n"
        "libfoo GPL-2.0 WITH Classpath-exception-2.0\n"
        "zlib-ng Zlib\n"
        "tool Apache-2.0 AND GPL-3.0\n"
    )
    expected = (
        "left-pad: ok: uses MIT\n"
        "express: ok: uses MIT\n"
        "libfoo: blocked: GPL-2.0 WITH Classpath-exception-2.0 (not allowed)\n"
        "zlib-ng: ok: uses Zlib\n"
        "tool: blocked: Apache-2.0 (not allowed), GPL-3.0 (not allowed)\n"
        "2 of 5 packages blocked\n"
    )
    assert _run(["check", "--allow", "MIT,Zlib", "--all", "-"], text.encode()) == (
        1,
        expected,
        "",
    )

    dependencies = tmp_path / "deps.txt"
    dependencies.write_text(text, encoding="utf-8", newline="\n")
    assert _run(
        ["check", "--allow", "MIT,Zlib", "--all", str(dependencies)]
    ) == (1, expected, "")


def test_check_all_accepted_report_matches_example_for_stdin_and_file(tmp_path):
    text = (
        "left-pad MIT\n"
        "express (MIT OR GPL-3.0)\n"
        "libfoo GPL-2.0 WITH Classpath-exception-2.0\n"
        "zlib-ng Zlib\n"
        "tool Apache-2.0 AND GPL-3.0\n"
    )
    expected = (
        "left-pad: ok: uses MIT\n"
        "express: ok: uses MIT\n"
        "libfoo: ok: uses GPL-2.0 WITH Classpath-exception-2.0\n"
        "zlib-ng: ok: uses Zlib\n"
        "tool: ok: uses Apache-2.0, GPL-3.0\n"
        "ok, 5 packages\n"
    )
    allow = "MIT,GPL-2.0,Zlib,Apache-2.0,GPL-3.0"
    assert _run(["check", "--allow", allow, "--all", "-"], text.encode()) == (
        0,
        expected,
        "",
    )

    dependencies = tmp_path / "deps.txt"
    dependencies.write_text(text, encoding="utf-8", newline="\n")
    assert _run(["check", "--allow", allow, "--all", str(dependencies)]) == (
        0,
        expected,
        "",
    )


def test_check_without_all_keeps_example_output_for_stdin_and_file(tmp_path):
    text = (
        "left-pad MIT\n"
        "express (MIT OR GPL-3.0)\n"
        "libfoo GPL-2.0 WITH Classpath-exception-2.0\n"
        "zlib-ng Zlib\n"
        "tool Apache-2.0 AND GPL-3.0\n"
    )
    expected = (
        "libfoo: blocked: GPL-2.0 WITH Classpath-exception-2.0 (not allowed)\n"
        "tool: blocked: Apache-2.0 (not allowed), GPL-3.0 (not allowed)\n"
        "2 of 5 packages blocked\n"
    )
    assert _run(["check", "--allow", "MIT,Zlib", "-"], text.encode()) == (
        1,
        expected,
        "",
    )

    dependencies = tmp_path / "deps.txt"
    dependencies.write_text(text, encoding="utf-8", newline="\n")
    assert _run(["check", "--allow", "MIT,Zlib", str(dependencies)]) == (
        1,
        expected,
        "",
    )


def test_check_all_flag_placements_repetition_and_policy_value_consumption():
    expected = (0, "a: ok: uses MIT\nok, 1 package\n", "")
    arguments = [
        ["check", "--all", "--allow", "MIT", "--deny", "GPL-3.0", "-"],
        ["check", "--allow", "MIT", "--all", "--deny", "GPL-3.0", "-", "--all"],
        [
            "check",
            "--allow",
            "MIT",
            "--deny",
            "GPL-3.0",
            "-",
            "--all",
            "--all",
            "--all",
        ],
    ]
    for argument_list in arguments:
        assert _run(argument_list, b"a MIT\n") == expected

    assert _run(["check", "--allow", "--all", "-"]) == _error(
        'invalid license "--all" in --allow'
    )


def test_check_all_empty_list():
    assert _run(["check", "--deny", "GPL-3.0", "--all", "-"]) == (
        0,
        "ok, 0 packages\n",
        "",
    )


def test_check_all_singular_list():
    assert _run(
        ["check", "--deny", "GPL-3.0", "--all", "-"], b"a MIT\n"
    ) == (0, "a: ok: uses MIT\nok, 1 package\n", "")


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["eval", "--all", "--allow", "MIT", "MIT"], 'unknown option "--all"'),
        (["ids", "--all", "LIST"], 'unknown option "--all"'),
        (["check", "--all=1", "--allow", "MIT", "LIST"], 'unknown option "--all=1"'),
        (["check", "--all"], "missing LIST"),
        (
            ["check", "--all", "LIST"],
            "no policy given (use --allow, --allow-file or --deny)",
        ),
    ],
)
def test_all_option_errors_preserve_status_streams_and_precedence(arguments, message):
    assert _run(arguments) == _error(message)
