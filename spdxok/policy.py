from dataclasses import dataclass, field

from spdxok.expr import ExprError, Leaf, parse_expression


@dataclass
class Policy:
    allow: set[Leaf] = field(default_factory=set)
    deny: set[Leaf] = field(default_factory=set)

    def reason(self, leaf: Leaf) -> str | None:
        denied = {_key(entry) for entry in self.deny}
        allowed = {_key(entry) for entry in self.allow}
        identity = _key(leaf)
        base_identity = (leaf.id.casefold(), None)

        if identity in denied or (leaf.exception is not None and base_identity in denied):
            return "denied"

        if not allowed:
            return None
        if identity in allowed or (leaf.exception is not None and base_identity in allowed):
            return None
        return "not allowed"


def parse_entry(text: str) -> Leaf:
    tree = parse_expression(text)
    if isinstance(tree, Leaf) and "(" not in text and ")" not in text:
        return tree
    raise ExprError("expected one license entry", 1)


def _key(leaf: Leaf) -> tuple[str, str | None]:
    return leaf.id.casefold(), leaf.exception.casefold() if leaf.exception is not None else None
