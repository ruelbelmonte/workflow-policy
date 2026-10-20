from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import LiteralScalarString

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


def text_lines(node: CommentedMap, key: str) -> Iterator[tuple[int, str]]:
    """Yield (file line, text) for each line of a string value, so findings land inside `run: |` blocks."""
    value = node.get(key)
    if not isinstance(value, str):
        return
    first = value_line(node, key) + (1 if isinstance(value, LiteralScalarString) else 0)
    for offset, text in enumerate(value.splitlines()):
        yield first + offset, text


def action_name(uses: str) -> str:
    """`owner/repo/path@ref` -> `owner/repo`, lowercased."""
    return "/".join(uses.split("@", 1)[0].split("/")[:2]).lower()
