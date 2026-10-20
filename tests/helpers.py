from __future__ import annotations

import re
from pathlib import Path

from workflow_policy.config import Config
from workflow_policy.loader import load_workflow
from workflow_policy.model import Finding, Workflow
from workflow_policy.rules import RULES

FIXTURES = Path(__file__).parent / "fixtures"
EXPECT = re.compile(r"#\s*expect:\s*(WP\d{3})")


def cases(rule_id: str, kind: str) -> list[Path]:
    return sorted((FIXTURES / rule_id.lower() / kind).glob("*.yml"))


def expected_lines(path: Path, rule_id: str) -> list[int]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [n for n, text in enumerate(lines, 1) for m in EXPECT.finditer(text) if m[1] == rule_id]


def load(path: Path) -> Workflow:
    wf = load_workflow(path, path.name)
    assert isinstance(wf, Workflow), wf
    return wf


def findings(rule_id: str, path: Path, config: Config = Config()) -> list[Finding]:
    return sorted(RULES[rule_id].check(load(path), config))


def lines(rule_id: str, path: Path, config: Config = Config()) -> list[int]:
    return [f.line for f in findings(rule_id, path, config)]
