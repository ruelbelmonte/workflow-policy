from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import FoldedScalarString, LiteralScalarString

if TYPE_CHECKING:
    from workflow_policy.config import Config


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    line: int
    rule: str
    message: str


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    rationale: str
    check: Callable[[Workflow, Config], Iterable[Finding]] = field(compare=False)


@dataclass
class Workflow:
    path: str
    data: CommentedMap

    def finding(self, rule: str, line: int, message: str) -> Finding:
        return Finding(self.path, line, rule, message)

    def triggers(self) -> dict[str, Any]:
        on = self.data.get("on")
        if isinstance(on, str):
            return {on: None}
        if isinstance(on, list):
            return {name: None for name in on if isinstance(name, str)}
        if isinstance(on, dict):
            return dict(on)
        return {}

    def jobs(self) -> Iterator[tuple[str, CommentedMap]]:
        jobs = self.data.get("jobs")
        if isinstance(jobs, CommentedMap):
            for job_id, job in jobs.items():
                if isinstance(job, CommentedMap):
                    yield job_id, job

    def steps(self) -> Iterator[tuple[str, CommentedMap]]:
        for job_id, job in self.jobs():
            steps = job.get("steps")
            if isinstance(steps, list):
                for step in steps:
                    if isinstance(step, CommentedMap):
                        yield job_id, step


def key_line(node: CommentedMap, key: str) -> int:
    return node.lc.key(key)[0] + 1


def value_line(node: CommentedMap, key: str) -> int:
    return node.lc.value(key)[0] + 1


@dataclass(frozen=True)
class Script:
    """A string value as the runner sees it (`text`), plus `view`: the same characters with folded
    line breaks restored, so a character offset maps to the file line it came from."""

    text: str
    view: str
    first_line: int

    def line_at(self, offset: int) -> int:
        return self.first_line + self.view.count("\n", 0, offset)

    def lines(self) -> Iterator[tuple[int, str]]:
        for offset, text in enumerate(self.view.splitlines()):
            yield self.first_line + offset, text


def script(node: CommentedMap, key: str) -> Script | None:
    value = node.get(key)
    if not isinstance(value, str):
        return None
    view = value
    if isinstance(value, FoldedScalarString):
        chars = list(value)
        for pos in getattr(value, "fold_pos", []):
            chars[pos] = "\n"
        view = "".join(chars)
    block = isinstance(value, (LiteralScalarString, FoldedScalarString))
    return Script(str(value), view, value_line(node, key) + (1 if block else 0))


def text_lines(node: CommentedMap, key: str) -> Iterator[tuple[int, str]]:
    found = script(node, key)
    if found:
        yield from found.lines()


# `${{ ... }}`, skipping over '...' string literals (with '' escapes) so a literal `}}` can't end it early.
EXPRESSION = re.compile(r"\$\{\{((?:[^'}]|'(?:[^']|'')*'|\}(?!\}))*)\}\}")
_INDEX_NAME = re.compile(r"""\[\s*['"]([\w-]+)['"]\s*\]""")
_INDEX_ANY = re.compile(r"\[\s*(?:\d+|\*)\s*\]")


def normalize_expression(text: str) -> str:
    """Lowercase (contexts are case-insensitive) and rewrite `['x']` as `.x` and `[0]` as `.*`."""
    text = _INDEX_NAME.sub(r".\1", text.lower())
    text = _INDEX_ANY.sub(".*", text)
    return re.sub(r"\s*\.\s*", ".", text)


def action_name(uses: str) -> str:
    """`owner/repo/path@ref` -> `owner/repo`, lowercased."""
    return "/".join(uses.split("@", 1)[0].split("/")[:2]).lower()
