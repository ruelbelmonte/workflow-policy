"""Every rule is driven by fixtures: tests/fixtures/<rule>/good/*.yml must be clean and each
line marked `# expect: <rule>` in tests/fixtures/<rule>/bad/*.yml must produce exactly one finding."""

import pytest

from helpers import FIXTURES, cases, expected_lines, lines
from workflow_policy.rules import RULES

FIXTURE_RULES = sorted(p.name.upper() for p in FIXTURES.iterdir() if p.is_dir())
BAD = [(r, p) for r in FIXTURE_RULES for p in cases(r, "bad")]
GOOD = [(r, p) for r in FIXTURE_RULES for p in cases(r, "good")]


@pytest.mark.parametrize(("rule_id", "path"), BAD, ids=lambda v: getattr(v, "name", v))
def test_bad_fixture_reports_marked_lines(rule_id, path):
    expected = expected_lines(path, rule_id)
    assert expected, f"{path} has no `# expect: {rule_id}` marker"
    assert lines(rule_id, path) == expected


@pytest.mark.parametrize(("rule_id", "path"), GOOD, ids=lambda v: getattr(v, "name", v))
def test_good_fixture_is_clean(rule_id, path):
    assert lines(rule_id, path) == []


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_every_rule_has_good_and_bad_fixtures(rule_id):
    assert cases(rule_id, "good") and cases(rule_id, "bad")


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_every_rule_documents_itself(rule_id):
    rule = RULES[rule_id]
    assert rule.title and rule.rationale and "\n" not in rule.rationale
