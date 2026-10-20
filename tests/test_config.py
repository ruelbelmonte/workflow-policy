from datetime import date
from pathlib import Path

import pytest

from workflow_policy.config import DEFAULT_WRITE_SCOPES, Config, load_config
from workflow_policy.engine import lint

TODAY = date(2026, 10, 20)
UNPINNED = """\
on: push
permissions: {}
jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      deployments: write
    steps:
      - uses: actions/checkout@v4
"""


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def config(tmp_path: Path, text: str):
    return load_config(write(tmp_path / "policy.yml", text), "policy.yml", TODAY)


def repo(tmp_path: Path, policy: str | None = None) -> Path:
    write(tmp_path / ".github/workflows/ci.yml", UNPINNED)
    if policy is not None:
        write(tmp_path / ".github/workflow-policy.yml", policy)
    return tmp_path


def rules(findings) -> list[str]:
    return [f.rule for f in findings]


def test_missing_file_gives_defaults(tmp_path):
    assert load_config(tmp_path / "absent.yml", "absent.yml", TODAY) == (Config(), [])


def test_full_config(tmp_path):
    cfg, errors = config(
        tmp_path,
        """\
disable: [WP007]
write-scopes: [deployments]
ignore:
  - path: .github/workflows/legacy-*.yml
    rules: [WP004]
    reason: vendor action has no releases
    expires: 2026-12-31
""",
    )
    assert errors == []
    assert cfg.disabled == {"WP007"}
    assert cfg.write_scopes == DEFAULT_WRITE_SCOPES | {"deployments"}
    (ignore,) = cfg.ignores
    assert ignore.rules == {"WP004"} and ignore.expires == date(2026, 12, 31)


@pytest.mark.parametrize(
    ("text", "line", "fragment"),
    [
        ("disable: [WP999]\n", 1, "unknown rule `WP999`"),
        ("disable: [WP000]\n", 1, "cannot be disabled"),
        ("disable: WP001\n", 1, "`disable` must be a list"),
        ("colour: blue\n", 1, "unknown key `colour`"),
        ("write-scopes: [1]\n", 1, "`write-scopes` must be a list of scope names"),
        ("- just a list\n", 1, "not a YAML mapping"),
        ("disable: [\n", 2, "cannot parse"),
        ("ignore: nope\n", 1, "`ignore` must be a list"),
        ("ignore:\n  - nope\n", 2, "must be a mapping"),
        (
            "ignore:\n  - path: a.yml\n    rules: [WP004]\n    expires: 2026-12-31\n",
            2,
            "needs a `reason`",
        ),
        (
            "ignore:\n  - path: a.yml\n    rules: [WP004]\n    reason: ok\n",
            2,
            "needs an `expires` date",
        ),
        (
            "ignore:\n  - path: a.yml\n    rules: [WP004]\n    reason: ok\n    expires: soon\n",
            5,
            "`expires` must be a YYYY-MM-DD date",
        ),
        (
            "ignore:\n  - rules: [WP004]\n    reason: ok\n    expires: 2026-12-31\n",
            2,
            "needs a `path`",
        ),
        (
            "ignore:\n  - path: a.yml\n    reason: ok\n    expires: 2026-12-31\n",
            2,
            "needs `rules`",
        ),
        (
            "ignore:\n  - path: a.yml\n    rules: [WP004, WP998]\n    reason: ok\n    expires: 2026-12-31\n",
            3,
            "unknown rule `WP998`",
        ),
        (
            "ignore:\n  - path: a.yml\n    rules: [WP004]\n    reason: ok\n    expires: 2026-12-31\n    note: x\n",
            2,
            "unknown key `note`",
        ),
    ],
)
def test_invalid_config_is_reported(tmp_path, text, line, fragment):
    _, errors = config(tmp_path, text)
    assert [(e.rule, e.line) for e in errors] == [("WP000", line)], errors
    assert fragment in errors[0].message


def test_expired_ignore_fails_and_stops_applying(tmp_path):
    cfg, errors = config(
        tmp_path,
        "ignore:\n  - path: a.yml\n    rules: [WP004]\n    reason: waiting on vendor\n    expires: 2026-10-19\n",
    )
    assert cfg.ignores == ()
    (error,) = errors
    assert error.line == 5 and "expired on 2026-10-19" in error.message and "waiting on vendor" in error.message


def test_ignore_expiring_today_still_applies(tmp_path):
    cfg, errors = config(
        tmp_path, "ignore:\n  - path: a.yml\n    rules: [WP004]\n    reason: ok\n    expires: '2026-10-20'\n"
    )
    assert errors == [] and len(cfg.ignores) == 1


def test_lint_applies_disable_allowlist_and_ignores(tmp_path):
    assert rules(lint(repo(tmp_path), today=TODAY)) == ["WP002", "WP004"]
    policy = """\
write-scopes: [deployments]
ignore:
  - path: .github/workflows/*.yml
    rules: [WP004]
    reason: tracked in issue 12
    expires: 2026-11-01
"""
    assert lint(repo(tmp_path, policy), today=TODAY) == []
    assert rules(lint(repo(tmp_path, "disable: [WP002, WP004]\n"), today=TODAY)) == []


def test_ignore_only_covers_matching_paths(tmp_path):
    policy = "ignore:\n  - path: .github/workflows/other.yml\n    rules: [WP004]\n    reason: x\n    expires: 2027-01-01\n"
    assert rules(lint(repo(tmp_path, policy), today=TODAY)) == ["WP002", "WP004"]


def test_explicit_missing_config_is_an_error(tmp_path):
    findings = lint(repo(tmp_path), config_path=tmp_path / "nope.yml", today=TODAY)
    assert sorted(rules(findings)) == ["WP000", "WP002", "WP004"]
    assert any(f.rule == "WP000" and f.path == "nope.yml" and "not found" in f.message for f in findings)
