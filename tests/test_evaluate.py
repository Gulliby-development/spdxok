import pytest

from spdxok.evaluate import Blocker, Evaluation, evaluate
from spdxok.expr import Leaf, parse_expression
from spdxok.policy import Policy


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("MIT", Evaluation(True, (Leaf("MIT"),), ())),
        ("Apache-2.0 WITH LLVM-exception", Evaluation(
            True, (Leaf("Apache-2.0", "LLVM-exception"),), ()
        )),
        ("MIT OR GPL-3.0", Evaluation(True, (Leaf("MIT"),), ())),
    ],
)
def test_satisfied_expressions_return_the_selected_licenses(expression, expected):
    assert evaluate(parse_expression(expression), Policy()) == expected


@pytest.mark.parametrize(
    ("expression", "policy", "expected"),
    [
        (
            "GPL-3.0",
            Policy(allow={Leaf("MIT")}),
            Evaluation(False, (), (Blocker(Leaf("GPL-3.0"), "not allowed"),)),
        ),
        (
            "GPL-3.0",
            Policy(allow={Leaf("GPL-3.0")}, deny={Leaf("GPL-3.0")}),
            Evaluation(False, (), (Blocker(Leaf("GPL-3.0"), "denied"),)),
        ),
        (
            "mit",
            Policy(allow={Leaf("MIT")}),
            Evaluation(True, (Leaf("mit"),), ()),
        ),
        (
            "MIT WITH LLVM-exception",
            Policy(allow={Leaf("MIT")}),
            Evaluation(True, (Leaf("MIT", "LLVM-exception"),), ()),
        ),
    ],
)
def test_leaf_satisfaction_and_blockers_use_policy_reasons(expression, policy, expected):
    assert evaluate(parse_expression(expression), policy) == expected


@pytest.mark.parametrize(
    ("expression", "allowed", "expected_uses"),
    [
        (
            "MIT AND Apache-2.0 AND BSD-3-Clause",
            {"MIT", "Apache-2.0", "BSD-3-Clause"},
            (Leaf("MIT"), Leaf("Apache-2.0"), Leaf("BSD-3-Clause")),
        ),
        (
            "A AND (B OR C) AND D",
            {"A", "B", "C", "D"},
            (Leaf("A"), Leaf("B"), Leaf("D")),
        ),
        (
            "(A OR B) AND (C OR D)",
            {"B", "C", "D"},
            (Leaf("B"), Leaf("C")),
        ),
    ],
)
def test_satisfied_and_uses_every_operand_in_left_to_right_order(
    expression, allowed, expected_uses
):
    policy = Policy(allow={Leaf(license_id) for license_id in allowed})

    assert evaluate(parse_expression(expression), policy) == Evaluation(True, expected_uses, ())


@pytest.mark.parametrize(
    ("expression", "allowed", "expected_blockers"),
    [
        (
            "MIT AND GPL-3.0 AND Apache-2.0",
            {"MIT"},
            (
                Blocker(Leaf("GPL-3.0"), "not allowed"),
                Blocker(Leaf("Apache-2.0"), "not allowed"),
            ),
        ),
        (
            "MIT AND (GPL-3.0 OR AGPL-3.0) AND BSD-3-Clause",
            {"ISC"},
            (
                Blocker(Leaf("MIT"), "not allowed"),
                Blocker(Leaf("GPL-3.0"), "not allowed"),
                Blocker(Leaf("AGPL-3.0"), "not allowed"),
                Blocker(Leaf("BSD-3-Clause"), "not allowed"),
            ),
        ),
    ],
)
def test_unsatisfied_and_collects_blockers_from_each_unsatisfied_operand(
    expression, allowed, expected_blockers
):
    policy = Policy(allow={Leaf(license_id) for license_id in allowed})
    result = evaluate(parse_expression(expression), policy)

    assert result == Evaluation(False, (), expected_blockers)


def test_unsatisfied_and_omits_blockers_from_satisfied_or_operands():
    result = evaluate(
        parse_expression("MIT AND (GPL-3.0 OR Apache-2.0) AND BSD-3-Clause"),
        Policy(allow={Leaf("Apache-2.0")}),
    )

    assert result == Evaluation(
        False,
        (),
        (
            Blocker(Leaf("MIT"), "not allowed"),
            Blocker(Leaf("BSD-3-Clause"), "not allowed"),
        ),
    )


@pytest.mark.parametrize(
    ("expression", "allowed", "expected_uses"),
    [
        ("MIT OR GPL-3.0", {"MIT", "GPL-3.0"}, (Leaf("MIT"),)),
        ("GPL-3.0 OR MIT", {"MIT"}, (Leaf("MIT"),)),
        ("GPL-3.0 OR (MIT AND ISC)", {"MIT", "ISC"}, (Leaf("MIT"), Leaf("ISC"))),
        (
            "GPL-3.0 OR (MIT AND (ISC OR BSD-3-Clause))",
            {"MIT", "ISC", "BSD-3-Clause"},
            (Leaf("MIT"), Leaf("ISC")),
        ),
    ],
)
def test_satisfied_or_uses_its_first_satisfied_operand(expression, allowed, expected_uses):
    policy = Policy(allow={Leaf(license_id) for license_id in allowed})

    assert evaluate(parse_expression(expression), policy) == Evaluation(True, expected_uses, ())


@pytest.mark.parametrize(
    ("expression", "expected_blockers"),
    [
        (
            "GPL-3.0 OR AGPL-3.0",
            (
                Blocker(Leaf("GPL-3.0"), "not allowed"),
                Blocker(Leaf("AGPL-3.0"), "not allowed"),
            ),
        ),
        (
            "MIT OR (GPL-3.0 AND Apache-2.0)",
            (
                Blocker(Leaf("MIT"), "not allowed"),
                Blocker(Leaf("GPL-3.0"), "not allowed"),
                Blocker(Leaf("Apache-2.0"), "not allowed"),
            ),
        ),
        (
            "(MIT OR Apache-2.0) OR (GPL-3.0 AND BSD-3-Clause)",
            (
                Blocker(Leaf("MIT"), "not allowed"),
                Blocker(Leaf("Apache-2.0"), "not allowed"),
                Blocker(Leaf("GPL-3.0"), "not allowed"),
                Blocker(Leaf("BSD-3-Clause"), "not allowed"),
            ),
        ),
    ],
)
def test_unsatisfied_or_collects_blockers_from_every_operand(expression, expected_blockers):
    result = evaluate(parse_expression(expression), Policy(allow={Leaf("ISC")}))

    assert result == Evaluation(False, (), expected_blockers)


@pytest.mark.parametrize(
    ("expression", "expected_blockers"),
    [
        (
            "GPL-3.0 OR gpl-3.0 OR Apache-2.0",
            (
                Blocker(Leaf("GPL-3.0"), "not allowed"),
                Blocker(Leaf("Apache-2.0"), "not allowed"),
            ),
        ),
        (
            (
                "GPL-3.0 WITH Classpath OR gpl-3.0 WITH classpath OR "
                "GPL-3.0 WITH LLVM OR GPL-3.0"
            ),
            (
                Blocker(Leaf("GPL-3.0", "Classpath"), "not allowed"),
                Blocker(Leaf("GPL-3.0", "LLVM"), "not allowed"),
                Blocker(Leaf("GPL-3.0"), "not allowed"),
            ),
        ),
        (
            "MIT AND (mit OR MIT) AND MIT",
            (Blocker(Leaf("MIT"), "not allowed"),),
        ),
    ],
)
def test_blockers_are_deduplicated_case_insensitively_in_first_seen_order(
    expression, expected_blockers
):
    result = evaluate(parse_expression(expression), Policy(allow={Leaf("ISC")}))

    assert result == Evaluation(False, (), expected_blockers)


def test_blockers_keep_distinct_license_exceptions():
    result = evaluate(
        parse_expression(
            "GPL-3.0 WITH Classpath OR GPL-3.0 WITH LLVM OR "
            "GPL-3.0 WITH classpath"
        ),
        Policy(allow={Leaf("ISC")}),
    )

    assert result == Evaluation(
        False,
        (),
        (
            Blocker(Leaf("GPL-3.0", "Classpath"), "not allowed"),
            Blocker(Leaf("GPL-3.0", "LLVM"), "not allowed"),
        ),
    )
