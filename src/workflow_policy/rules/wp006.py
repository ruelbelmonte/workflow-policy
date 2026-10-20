from __future__ import annotations

import re
from collections.abc import Iterator

from workflow_policy.config import Config
from workflow_policy.model import EXPRESSION, Finding, Rule, Workflow, normalize_expression, script


def _expand(*fields: str) -> list[str]:
    out = []
    for field in fields:
        out += [field.replace("{who}", who) for who in ("author", "committer")] if "{who}" in field else [field]
    return ["github." + f for f in out]


UNTRUSTED_FIELDS = _expand(
    "head_ref",
    "event.issue.title",
    "event.issue.body",
    "event.pull_request.title",
    "event.pull_request.body",
    "event.discussion.title",
    "event.discussion.body",
    "event.comment.body",
    "event.review.body",
    "event.review_comment.body",
    "event.pages.*.page_name",
    "event.commits.*.message",
    "event.commits.*.{who}.email",
    "event.commits.*.{who}.name",
    "event.head_commit.message",
    "event.head_commit.{who}.email",
    "event.head_commit.{who}.name",
    "event.pull_request.head.ref",
    "event.pull_request.head.label",
    "event.pull_request.head.repo.default_branch",
    "event.workflow_run.head_branch",
    "event.workflow_run.display_title",
    "event.workflow_run.head_commit.message",
    "event.workflow_run.head_commit.{who}.email",
    "event.workflow_run.head_commit.{who}.name",
)
# A whole object (`toJSON(github.event)`, `github.event.issue`) carries its untrusted fields with it.
ANCESTORS = {f.rsplit(".", n)[0] for f in UNTRUSTED_FIELDS for n in range(1, f.count("."))} | {"github"}
PATH = re.compile(r"(?<![\w.-])github(?:\.(?:[\w-]+|\*))*")


def untrusted(path: str) -> bool:
    return path in ANCESTORS or any(path == f or path.startswith(f + ".") for f in UNTRUSTED_FIELDS)


def env_name(path: str) -> str:
    parts = [p for p in path.split(".") if p not in {"github", "event", "*"}] or ["event"]
    return "_".join(parts[-2:]).upper().replace("-", "_")


def check(wf: Workflow, config: Config) -> Iterator[Finding]:
    for _, step in wf.steps():
        run = script(step, "run")
        if run is None:
            continue
        for expr in EXPRESSION.finditer(run.text):
            inner = " ".join(expr[1].split())
            for path in PATH.findall(normalize_expression(expr[1])):
                if untrusted(path):
                    name = env_name(path)
                    yield wf.finding(
                        "WP006",
                        run.line_at(expr.start()),
                        f"`${{{{ {inner} }}}}` is attacker-controlled and is expanded into the script before the shell "
                        f'runs it; pass it through the environment instead: `env: {name}: ${{{{ {inner} }}}}` and use `"${name}"`',
                    )
                    break


RULE = Rule(
    "WP006",
    "No user-controlled `github.event` fields in `run:`",
    "`${{ }}` is substituted into the script text, so a crafted issue title or branch name becomes shell code.",
    check,
)
