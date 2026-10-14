from dataclasses import dataclass, field


class ExprError(ValueError):
    def __init__(self, message: str, column: int) -> None:
        self.message = message
        self.column = column
        super().__init__(f"{message} (column {column})")


@dataclass(frozen=True, slots=True)
class Leaf:
    id: str
    exception: str | None = None


@dataclass(frozen=True, slots=True)
class And:
    items: tuple["Expression", ...]


@dataclass(frozen=True, slots=True)
class Or:
    items: tuple["Expression", ...]


Expression = Leaf | And | Or


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    column: int


@dataclass(slots=True)
class _Frame:
    opening: _Token | None = None
    or_items: list[Expression] = field(default_factory=list)
    and_items: list[Expression] = field(default_factory=list)
    expect_operand: bool = True


class _Parser:
    def __init__(self, text: str) -> None:
        self.text = text.strip(" \t")
        self.position = 0
        self._lookahead: _Token | None = None
        self._looked_ahead = False

    def parse(self) -> Expression:
        if not self.text:
            raise ExprError("empty expression", 1)

        frames = [_Frame()]
        while True:
            frame = frames[-1]
            token = self._peek()

            if frame.expect_operand:
                if token is None or token.kind in {"AND", "OR", "WITH", "RPAREN"}:
                    raise self._expected("a license", token)
                if token.kind == "LPAREN":
                    opening = self._take()
                    frames.append(_Frame(opening))
                    continue

                identifier = self._take()
                exception: str | None = None
                token = self._peek()
                if token is not None and token.kind == "WITH":
                    self._take()
                    exception_token = self._peek()
                    if exception_token is None or exception_token.kind != "IDENT":
                        raise self._expected("an exception", exception_token)
                    exception = self._take().text
                frame.and_items.append(Leaf(identifier.text, exception))
                frame.expect_operand = False
                continue

            if token is None:
                if frame.opening is not None:
                    raise ExprError('missing ")"', frame.opening.column)
                return _finish_or(frame)

            if token.kind == "AND":
                self._take()
                frame.expect_operand = True
                continue
            if token.kind == "OR":
                self._take()
                frame.or_items.append(_finish_and(frame.and_items))
                frame.and_items.clear()
                frame.expect_operand = True
                continue
            if token.kind == "RPAREN":
                if frame.opening is None:
                    raise ExprError('unmatched ")"', token.column)
                self._take()
                tree = _finish_or(frame)
                frames.pop()
                parent = frames[-1]
                parent.and_items.append(tree)
                parent.expect_operand = False
                continue
            raise ExprError(f'unexpected "{token.text}"', token.column)

    def _expected(self, expected: str, token: _Token | None) -> ExprError:
        if token is None:
            found = "end of expression"
            column = len(self.text) + 1
        else:
            found = f'"{token.text}"'
            column = token.column
        return ExprError(f"expected {expected}, found {found}", column)

    def _expected(self, expected: str, token: _Token | None) -> ExprError:
        if token is None:
            found = "end of expression"
            column = len(self.text) + 1
        else:
            found = f'"{token.text}"'
            column = token.column
        return ExprError(f"expected {expected}, found {found}", column)

    def _take(self) -> _Token:
        token = self._peek()
        if token is None:
            raise RuntimeError("cannot consume end of expression")
        self._lookahead = None
        self._looked_ahead = False
        return token

    def _peek(self) -> _Token | None:
        if not self._looked_ahead:
            self._lookahead = self._scan()
            self._looked_ahead = True
        return self._lookahead

    def _scan(self) -> _Token | None:
        while self.position < len(self.text) and self.text[self.position] in " \t":
            self.position += 1

        if self.position >= len(self.text):
            return None

        start = self.position
        char = self.text[self.position]
        if char == "(":
            self.position += 1
            return _Token("LPAREN", char, start + 1)
        if char == ")":
            self.position += 1
            return _Token("RPAREN", char, start + 1)
        if _is_ascii_alphanumeric(char):
            self.position += 1
            while self.position < len(self.text) and _is_id_character(self.text[self.position]):
                self.position += 1
            if self.position < len(self.text) and self.text[self.position] == "+":
                self.position += 1
            value = self.text[start : self.position]
            if value in {"AND", "OR", "WITH"}:
                return _Token(value, value, start + 1)
            return _Token("IDENT", value, start + 1)

        raise ExprError(f'unexpected character "{char}"', start + 1)


def _finish_and(items: list[Expression]) -> Expression:
    if len(items) == 1:
        return items[0]
    return And(tuple(items))


def _finish_or(frame: _Frame) -> Expression:
    items = [*frame.or_items, _finish_and(frame.and_items)]
    if len(items) == 1:
        return items[0]
    return Or(tuple(items))


def _is_ascii_alphanumeric(char: str) -> bool:
    return "A" <= char <= "Z" or "a" <= char <= "z" or "0" <= char <= "9"


def _is_id_character(char: str) -> bool:
    return _is_ascii_alphanumeric(char) or char in ".-"


def parse_expression(text: str) -> Expression:
    return _Parser(text).parse()


def leaves(tree: Expression) -> list[Leaf]:
    if isinstance(tree, Leaf):
        return [tree]
    result: list[Leaf] = []
    for item in tree.items:
        result.extend(leaves(item))
    return result
