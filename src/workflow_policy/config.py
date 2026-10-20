from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from fnmatch import fnmatchcase
from pathlib import Path

from ruamel.yaml.comments import CommentedMap

from workflow_policy.loader import load_yaml
from workflow_policy.model import Finding, key_line, value_line

DEFAULT_WRITE_SCOPES = frozenset(
    {"contents", "packages", "id-token", "security-events", "pull-requests", "issues"}
)
TOP_KEYS = {"disable", "write-scopes", "ignore"}
IGNORE_KEYS = {"path", "rules", "reason", "expires"}


@dataclass(frozen=True)
class Ignore:
    path: str
    rules: frozenset[str]
    reason: str
    expires: date

    def covers(self, finding: Finding) -> bool:
        return finding.rule in self.rules and fnmatchcase(finding.path, self.path)


@dataclass(frozen=True)
class Config:
    disabled: frozenset[str] = frozenset()
    write_scopes: frozenset[str] = DEFAULT_WRITE_SCOPES
    ignores: tuple[Ignore, ...] = ()

    def ignored(self, finding: Finding) -> bool:
        return any(ignore.covers(finding) for ignore in self.ignores)


class _Errors(list):
    def __init__(self, display: str):
        super().__init__()
        self.display = display

    def add(self, line: int, message: str) -> None:
        self.append(Finding(self.display, line, "WP000", message))


def _rule_ids(value: object, line: int, key: str, errors: _Errors) -> frozenset[str] | None:
    from workflow_policy.rules import RULES

    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.add(line, f"`{key}` must be a list of rule IDs")
        return None
    start = len(errors)
    for rule_id in value:
        if rule_id == "WP000":
            errors.add(line, "WP000 (policy errors) cannot be disabled or ignored")
        elif rule_id not in RULES:
            errors.add(line, f"unknown rule `{rule_id}` in `{key}`; known rules: {', '.join(sorted(RULES))}")
    return frozenset(value) if len(errors) == start else None


def _ignore(entry: object, line: int, today: date, errors: _Errors) -> Ignore | None:
    if not isinstance(entry, CommentedMap):
        errors.add(line, "each `ignore` entry must be a mapping with path, rules, reason and expires")
        return None
    start = len(errors)
    for key in entry:
        if key not in IGNORE_KEYS:
            errors.add(line, f"unknown key `{key}` in `ignore` entry; expected {', '.join(sorted(IGNORE_KEYS))}")
    path, reason, expires = entry.get("path"), entry.get("reason"), entry.get("expires")
    if not isinstance(path, str) or not path:
        errors.add(line, "`ignore` entry needs a `path` (a glob relative to the repository root)")
    if "rules" not in entry:
        errors.add(line, "`ignore` entry needs `rules`, the rule IDs it suppresses")
        rules = None
    else:
        rules = _rule_ids(entry["rules"], value_line(entry, "rules"), "rules", errors)
    if not isinstance(reason, str) or not reason.strip():
        errors.add(line, "`ignore` entry needs a `reason` explaining why the finding is accepted")
    if expires is None:
        errors.add(line, "`ignore` entry needs an `expires` date (YYYY-MM-DD) so it is revisited")
    elif not isinstance(expires, date):
        try:
            expires = date.fromisoformat(str(expires))
        except ValueError:
            errors.add(value_line(entry, "expires"), "`expires` must be a YYYY-MM-DD date")
    if len(errors) > start or rules is None:
        return None
    if expires < today:
        errors.add(
            value_line(entry, "expires"),
            f"ignore of {', '.join(sorted(rules))} for `{path}` expired on {expires.isoformat()} "
            f"(reason: {reason.strip()}); fix the findings or renew it with a new date",
        )
        return None
    return Ignore(path, rules, reason.strip(), expires)


def load_config(path: Path, display: str, today: date) -> tuple[Config, list[Finding]]:
    if not path.is_file():
        return Config(), []
    data = load_yaml(path, display)
    if isinstance(data, Finding):
        return Config(), [data]
    errors = _Errors(display)
    for key in data:
        if key not in TOP_KEYS:
            errors.add(key_line(data, key), f"unknown key `{key}`; expected {', '.join(sorted(TOP_KEYS))}")

    disabled = frozenset()
    if "disable" in data:
        if isinstance(data["disable"], list):
            disabled = _rule_ids(data["disable"], key_line(data, "disable"), "disable", errors) or frozenset()
        else:
            errors.add(key_line(data, "disable"), "`disable` must be a list of rule IDs")

    write_scopes = DEFAULT_WRITE_SCOPES
    if "write-scopes" in data:
        extra = data["write-scopes"]
        if isinstance(extra, list) and all(isinstance(s, str) for s in extra):
            write_scopes = DEFAULT_WRITE_SCOPES | set(extra)
        else:
            errors.add(key_line(data, "write-scopes"), "`write-scopes` must be a list of scope names")

    ignores: list[Ignore] = []
    if "ignore" in data:
        entries = data["ignore"]
        if isinstance(entries, list):
            for i, entry in enumerate(entries):
                if ignore := _ignore(entry, entries.lc.item(i)[0] + 1, today, errors):
                    ignores.append(ignore)
        else:
            errors.add(key_line(data, "ignore"), "`ignore` must be a list of entries")

    return Config(disabled, write_scopes, tuple(ignores)), list(errors)
