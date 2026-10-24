import sys
from collections.abc import Sequence
from typing import BinaryIO, TextIO

from spdxok.evaluate import Evaluation, evaluate
from spdxok.expr import ExprError, parse_expression
from spdxok.listing import ListError, Package, _physical_lines, parse_list
from spdxok.policy import Policy, parse_entry
from spdxok.report import check_report, error_report, evaluation_report, ids_report, usage


class _CLIError(Exception):
    pass


def _display_path(path: str) -> str:
    return path.replace("\\", "/")


def _parse_policy_entry(text: str):
    if "(" in text or ")" in text:
        raise ValueError("parentheses are not allowed in a policy entry")
    return parse_entry(text)


def _option(argument: str) -> tuple[str | None, str | None]:
    for option in ("--allow", "--allow-file", "--deny"):
        if argument == option:
            return option, None
        prefix = f"{option}="
        if argument.startswith(prefix):
            return option, argument[len(prefix) :]
    return None, None


def _read_file(path: str) -> bytes:
    try:
        with open(path, "rb") as input_file:
            return input_file.read()
    except (OSError, ValueError) as error:
        raise _CLIError(f"{_display_path(path)}: cannot read the file") from error


def _decode(data: bytes, display: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _CLIError(f"{display}: input is not valid UTF-8") from error


def _load_allow_file(path: str, policy: Policy) -> None:
    display = _display_path(path)
    text = _decode(_read_file(path), display)
    for line_number, physical_line in enumerate(_physical_lines(text), start=1):
        entry = physical_line.strip(" \t")
        if not entry or entry.startswith("#"):
            continue
        try:
            policy.allow.add(_parse_policy_entry(entry))
        except ValueError as error:
            raise _CLIError(f'{display}:{line_number}: invalid license "{entry}"') from error


def _parse_minimum(value: str) -> int:
    if not value.isascii() or not value.isdigit() or value.strip("0") == "" or len(value) > 9:
        raise _CLIError(f'invalid --min "{value}"')
    return int(value)


def _parse_arguments(
    arguments: Sequence[str],
) -> tuple[str, str, Policy, list[str], bool, int]:
    if not arguments:
        raise _CLIError("missing command (eval, check or ids)")

    command = arguments[0]
    if command == "--help":
        raise _CLIError('unknown option "--help"')
    if command not in {"eval", "check", "ids"}:
        raise _CLIError(f'unknown command "{command}"')

    allow_files: list[str] = []
    policy = Policy()
    policy_given = False
    positional: str | None = None
    include_all = False
    minimum = 1
    index = 1
    while index < len(arguments):
        argument = arguments[index]
        option, value = _option(argument)
        if option is not None:
            if command == "ids":
                raise _CLIError(f'unknown option "{argument}"')
            if value is None:
                if index + 1 >= len(arguments):
                    raise _CLIError(f"{option} needs a value")
                index += 1
                value = arguments[index]
                if value == "--help":
                    raise _CLIError('unknown option "--help"')
            policy_given = True
            if option == "--allow-file":
                allow_files.append(value)
            else:
                target = policy.allow if option == "--allow" else policy.deny
                for raw_entry in value.split(","):
                    entry = raw_entry.strip(" \t")
                    try:
                        target.add(_parse_policy_entry(entry))
                    except ValueError as error:
                        raise _CLIError(
                            f'invalid license "{entry}" in {option}'
                        ) from error
        elif argument == "--min" or argument.startswith("--min="):
            if command != "ids":
                raise _CLIError(f'unknown option "{argument}"')
            if argument == "--min":
                if index + 1 >= len(arguments):
                    raise _CLIError("--min needs a value")
                index += 1
                value = arguments[index]
            else:
                value = argument[len("--min=") :]
            minimum = _parse_minimum(value)
        elif argument == "--all":
            if command != "check":
                raise _CLIError(f'unknown option "{argument}"')
            include_all = True
        elif argument.startswith("-") and argument != "-":
            raise _CLIError(f'unknown option "{argument}"')
        elif positional is None:
            positional = argument
        else:
            raise _CLIError("too many arguments")
        index += 1

    if positional is None:
        if command == "eval":
            raise _CLIError("missing EXPRESSION")
        raise _CLIError("missing LIST")
    if command != "ids" and not policy_given:
        raise _CLIError("no policy given (use --allow, --allow-file or --deny)")
    return command, positional, policy, allow_files, include_all, minimum


def _read_list(
    path: str, stdin: BinaryIO
) -> tuple[str, list[Package]]:
    if path == "-":
        display = "<stdin>"
        try:
            data = stdin.read()
        except OSError as error:
            raise _CLIError(f"{display}: cannot read the file") from error
    else:
        display = _display_path(path)
        data = _read_file(path)
    text = _decode(data, display)
    try:
        return display, parse_list(display, text)
    except ListError as error:
        raise _CLIError(str(error)) from error


def main(
    argv: Sequence[str],
    stdin: BinaryIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = sys.stdout if stdout is None else stdout
    errors = sys.stderr if stderr is None else stderr
    input_stream = sys.stdin.buffer if stdin is None else stdin

    if list(argv) == ["--help"]:
        output.write(usage())
        return 0

    try:
        command, positional, policy, allow_files, include_all, minimum = _parse_arguments(argv)
        for allow_file in allow_files:
            _load_allow_file(allow_file, policy)

        if command == "eval":
            try:
                tree = parse_expression(positional)
            except ExprError as error:
                raise _CLIError(f"invalid expression: {error}") from error
            result = evaluate(tree, policy)
            output.write(evaluation_report(result))
            return 0 if result.satisfied else 1

        _, packages = _read_list(positional, input_stream)
        if command == "check":
            results: list[Evaluation] = [evaluate(package.expression, policy) for package in packages]
            report, status = check_report(packages, results, include_all)
            output.write(report)
            return status

        output.write(ids_report(packages, minimum))
        return 0
    except _CLIError as error:
        errors.write(error_report(str(error)))
        return 2
