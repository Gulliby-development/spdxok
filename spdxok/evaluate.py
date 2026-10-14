from collections.abc import Iterable
from dataclasses import dataclass

from spdxok.expr import And, Expression, Leaf
from spdxok.policy import Policy


@dataclass(frozen=True, slots=True)
class Blocker:
    leaf: Leaf
    reason: str


@dataclass(frozen=True, slots=True)
class Evaluation:
    satisfied: bool
    uses: tuple[Leaf, ...]
    blockers: tuple[Blocker, ...]


def evaluate(tree: Expression, policy: Policy) -> Evaluation:
    """Evaluate an expression and retain its selected licenses or blocking leaves."""
    if isinstance(tree, Leaf):
        reason = policy.reason(tree)
        if reason is None:
            return Evaluation(True, (tree,), ())
        return Evaluation(False, (), (Blocker(tree, reason),))

    child_results = [evaluate(item, policy) for item in tree.items]
    if isinstance(tree, And):
        if all(result.satisfied for result in child_results):
            uses = tuple(leaf for result in child_results for leaf in result.uses)
            return Evaluation(True, uses, ())
        blockers = (
            blocker
            for result in child_results
            if not result.satisfied
            for blocker in result.blockers
        )
        return Evaluation(False, (), _unique_blockers(blockers))

    for result in child_results:
        if result.satisfied:
            return Evaluation(True, result.uses, ())
    blockers = (blocker for result in child_results for blocker in result.blockers)
    return Evaluation(False, (), _unique_blockers(blockers))


def _unique_blockers(blockers: Iterable[Blocker]) -> tuple[Blocker, ...]:
    unique: list[Blocker] = []
    seen: set[tuple[str, str | None]] = set()
    for blocker in blockers:
        key = (
            blocker.leaf.id.casefold(),
            blocker.leaf.exception.casefold() if blocker.leaf.exception is not None else None,
        )
        if key not in seen:
            seen.add(key)
            unique.append(blocker)
    return tuple(unique)
