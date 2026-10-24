from collections.abc import Sequence

from spdxok.evaluate import Evaluation
from spdxok.expr import Leaf, leaves
from spdxok.listing import Package

_USAGE = (
    "usage: spdxok eval [--allow IDS]... [--allow-file FILE]... [--deny IDS]... EXPRESSION\n"
    "       spdxok check [--allow IDS]... [--allow-file FILE]... [--deny IDS]... [--all] LIST\n"
    "       spdxok ids [--min COUNT] LIST\n"
)


def usage() -> str:
    return _USAGE


def format_leaf(leaf: Leaf) -> str:
    if leaf.exception is None:
        return leaf.id
    return f"{leaf.id} WITH {leaf.exception}"


def error_report(message: str) -> str:
    return f"spdxok: {message}\n"


def evaluation_report(result: Evaluation) -> str:
    if result.satisfied:
        uses = ", ".join(format_leaf(leaf) for leaf in result.uses)
        return f"ok: uses {uses}\n"
    blockers = ", ".join(
        f"{format_leaf(blocker.leaf)} ({blocker.reason})" for blocker in result.blockers
    )
    return f"blocked: {blockers}\n"


def check_report(
    packages: Sequence[Package],
    evaluations: Sequence[Evaluation],
    include_all: bool = False,
) -> tuple[str, int]:
    lines: list[str] = []
    blocked = 0
    for package, result in zip(packages, evaluations):
        if result.satisfied:
            if include_all:
                lines.append(f"{package.name}: {evaluation_report(result)[:-1]}")
            continue
        blocked += 1
        blockers = ", ".join(
            f"{format_leaf(blocker.leaf)} ({blocker.reason})" for blocker in result.blockers
        )
        lines.append(f"{package.name}: blocked: {blockers}")

    total = len(packages)
    suffix = "package" if total == 1 else "packages"
    if blocked:
        lines.append(f"{blocked} of {total} {suffix} blocked")
        return "\n".join(lines) + "\n", 1
    lines.append(f"ok, {total} {suffix}")
    return "\n".join(lines) + "\n", 0


def ids_report(packages: Sequence[Package], minimum: int = 1) -> str:
    spellings: dict[tuple[str, str | None], str] = {}
    counts: dict[tuple[str, str | None], int] = {}
    for package in packages:
        package_keys: set[tuple[str, str | None]] = set()
        for leaf in leaves(package.expression):
            key = _license_key(leaf)
            spellings.setdefault(key, format_leaf(leaf))
            package_keys.add(key)
        for key in package_keys:
            counts[key] = counts.get(key, 0) + 1

    ordered = sorted(
        counts,
        key=lambda key: (-counts[key], spellings[key].lower().encode("utf-8")),
    )
    shown = [key for key in ordered if counts[key] >= minimum]
    width = max((len(str(counts[key])) for key in shown), default=1)
    lines = [f"{counts[key]:>{width}}  {spellings[key]}" for key in shown]
    license_count = len(ordered)
    license_word = "license" if license_count == 1 else "licenses"
    package_word = "package" if len(packages) == 1 else "packages"
    prefix = f"{len(shown)} of " if len(shown) < license_count else ""
    lines.append(
        f"{prefix}{license_count} distinct {license_word} in {len(packages)} {package_word}"
    )
    return "\n".join(lines) + "\n"


def _license_key(leaf: Leaf) -> tuple[str, str | None]:
    return (
        leaf.id.casefold(),
        leaf.exception.casefold() if leaf.exception is not None else None,
    )
