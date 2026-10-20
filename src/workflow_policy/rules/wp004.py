from __future__ import annotations

import re
from collections.abc import Iterator

from ruamel.yaml.comments import CommentedMap

from workflow_policy.config import Config
from workflow_policy.model import Finding, Rule, Workflow, value_line

# Lowercase is the only canonical SHA form; anything else may resolve as a branch or tag of that name.
FULL_SHA = re.compile(r"[0-9a-f]{40}")
DOCKER_DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def problem(uses: str) -> str | None:
    if uses.startswith("./"):
        return None
    if uses.startswith("docker://"):
        if DOCKER_DIGEST.search(uses):
            return None
        return f"`{uses}` is not pinned to an image digest; use `{uses.split('@')[0]}@sha256:<digest>`"
    name, _, ref = uses.partition("@")
    if FULL_SHA.fullmatch(ref):
        return None
    hint = f" # {ref}" if ref else ""
    return f"`{uses}` is not pinned to a full 40-character commit SHA; use `{name}@<sha>{hint}`"


def check(wf: Workflow, config: Config) -> Iterator[Finding]:
    nodes: list[CommentedMap] = [job for _, job in wf.jobs()] + [step for _, step in wf.steps()]
    for node in nodes:
        uses = node.get("uses")
        if isinstance(uses, str) and (message := problem(uses)):
            yield wf.finding("WP004", value_line(node, "uses"), message)


RULE = Rule(
    "WP004",
    "Third-party actions must be pinned to a commit SHA",
    "Tags and branches are mutable, so whoever controls the action's repository controls what your job runs.",
    check,
)
