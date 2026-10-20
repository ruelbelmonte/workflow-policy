from __future__ import annotations

import os
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

from workflow_policy.config import load_config
from workflow_policy.loader import load_workflow
from workflow_policy.model import Finding
from workflow_policy.rules import RULES

DEFAULT_CONFIG = ".github/workflow-policy.yml"


def workflow_files(root: Path) -> list[Path]:
    folder = root / ".github" / "workflows"
    return sorted(p for p in folder.glob("*") if p.suffix in {".yml", ".yaml"} and p.is_file())


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _display_prefix(root: Path) -> str:
    """Annotations and SARIF want paths relative to the checkout (the cwd), not to `root`."""
    try:
        prefix = root.resolve().relative_to(Path(os.getcwd()).resolve()).as_posix()
    except ValueError:
        return ""
    return "" if prefix == "." else prefix + "/"


def lint(root: Path, config_path: Path | None = None, today: date | None = None) -> list[Finding]:
    today = today or datetime.now(timezone.utc).date()
    errors: list[Finding] = []
    if config_path is not None and not config_path.is_file():
        errors.append(Finding(_relative(config_path, root), 1, "WP000", "config file not found"))
        config_path = None
    path = config_path or root / DEFAULT_CONFIG
    config, config_errors = load_config(path, _relative(path, root), today)
    errors += config_errors

    findings: list[Finding] = []
    for file in workflow_files(root):
        wf = load_workflow(file, _relative(file, root))
        if isinstance(wf, Finding):
            errors.append(wf)
            continue
        for rule_id, rule in RULES.items():
            if rule_id not in config.disabled:
                findings += [f for f in rule.check(wf, config) if not config.ignored(f)]

    prefix = _display_prefix(root)
    return sorted(replace(f, path=prefix + f.path) for f in errors + findings)
