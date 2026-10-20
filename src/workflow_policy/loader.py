from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from workflow_policy.model import Finding, Workflow


def load_yaml(path: Path, display: str) -> CommentedMap | Finding:
    try:
        data = YAML(typ="rt", pure=True).load(path.read_text(encoding="utf-8"))
    except YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 1 if mark is not None else 1
        problem = getattr(exc, "problem", None) or str(exc).splitlines()[0]
        return Finding(display, line, "WP000", f"cannot parse YAML: {problem}")
    if not isinstance(data, CommentedMap):
        return Finding(display, 1, "WP000", "file is not a YAML mapping")
    return data


def load_workflow(path: Path, display: str) -> Workflow | Finding:
    data = load_yaml(path, display)
    return data if isinstance(data, Finding) else Workflow(display, data)
