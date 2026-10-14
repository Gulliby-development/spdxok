<p align="center"><img src="docs/logo.svg" width="96" alt="" /></p>

# spdxok

spdxok checks the SPDX-style license expressions in dependency reports against a policy you define. It is for project maintainers who need to keep dependencies within license rules and want a check that can fail in CI. It does not provide a license catalog or license texts.

[![CI](https://github.com/Gulliby-development/spdxok/actions/workflows/ci.yml/badge.svg)](https://github.com/Gulliby-development/spdxok/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Install

From the project root, install the package with:

`pip install .`

You can also run it directly from the project root with `python -m spdxok`.

## Usage

The command has three operations:

```text
usage: spdxok eval [--allow IDS]... [--allow-file FILE]... [--deny IDS]... EXPRESSION
       spdxok check [--allow IDS]... [--allow-file FILE]... [--deny IDS]... LIST
       spdxok ids LIST
```

Use `eval` to check one quoted expression, for example:

`python -m spdxok eval --allow MIT "MIT OR GPL-3.0"`

Use `check` to check each package in a list. Add a step like this to your CI job so a blocked package fails the job:

```yaml
- name: Check dependency licenses
  run: python -m spdxok check --allow MIT,ISC,Zlib --allow Apache-2.0 --deny AGPL-3.0 deps.txt
```

For example, with this `deps.txt`:

```text
# dependency licenses
left-pad MIT
express (MIT OR GPL-3.0)
lodash MIT AND (ISC OR BSD-3-Clause)
libfoo GPL-2.0 WITH Classpath-exception-2.0
zlib-ng Zlib
readline GPL-3.0+ OR AGPL-3.0
tool Apache-2.0 AND GPL-3.0
```

the check prints:

```text
libfoo: blocked: GPL-2.0 WITH Classpath-exception-2.0 (not allowed)
readline: blocked: GPL-3.0+ (not allowed), AGPL-3.0 (denied)
tool: blocked: GPL-3.0 (not allowed)
3 of 7 packages blocked
```

Use `ids` to count licenses used by packages in the list:

```text
3  MIT
2  GPL-3.0
1  AGPL-3.0
1  Apache-2.0
1  BSD-3-Clause
1  GPL-2.0 WITH Classpath-exception-2.0
1  GPL-3.0+
1  ISC
1  Zlib
9 distinct licenses in 7 packages
```

For standard input, use `-` in place of the list path. The `--allow`, `--deny`, and `--allow-file` options can be repeated. Inline ID lists are comma-separated; allow files contain one license entry per line.

## Expressions

An expression contains license identifiers joined by uppercase `AND` and `OR`, with parentheses for grouping. `AND` binds more tightly than `OR`. A license can have an exception using `WITH`, as in `GPL-2.0 WITH Classpath-exception-2.0`. Identifiers and exception names are case-insensitive; a trailing `+` is part of an identifier. Spaces and tabs may surround tokens.

## Policy

An allow policy is unrestricted when it has no allowed licenses. Otherwise, a license must be allowed explicitly, unless it has an exception and its base license is allowed. Deny rules use the same exception inheritance, and denial takes precedence over allowance. Entries are one license, optionally followed by `WITH` and one exception; an expression with `OR` or `AND` is not a policy entry.

An allow file has one entry per line. Blank lines and lines beginning with `#` are ignored. Package list files contain one `NAME EXPRESSION` record per line; blank lines and comment lines are ignored. The expression is the remainder of the line after the package name.

## Exit codes

- `0`: the expression or package list passes, or license counts are printed.
- `1`: an expression or one or more packages are blocked.
- `2`: a usage, input, or syntax error occurred.

## Development

Run the tests with `pytest -q` (or `python -m pytest -q`) and lint the project with `ruff check .` (or `python -m ruff check .`).

## License

MIT, see [LICENSE](LICENSE).

---

Built with BAKED.
