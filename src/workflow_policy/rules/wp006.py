from __future__ import annotations

import re
from collections.abc import Iterator

from workflow_policy.config import Config
from workflow_policy.model import Finding, Rule, Workflow, text_lines

INDEX = r"(?:\.\*|\[[^\]]*\])"
AUTHOR = r"(?:author|committer)\.(?:email|name)"
EVENT_FIELDS = [
    r"(?:issue|pull_request|discussion)\.(?:title|body)",
    r"(?:comment|review|review_comment)\.body",
    rf"pages{INDEX}\.page_name",
    rf"commits{INDEX}\.(?:message|{AUTHOR})",
    rf"head_commit\.(?:message|{AUTHOR})",
    r"pull_request\.head\.(?:ref|label|repo\.default_branch)",
    rf"workflow_run\.(?:head_branch|display_title|head_commit\.(?:message|{AUTHOR}))",
]
UNTRUSTED = re.compile(r"github\.(?:head_ref|event\.(?:" + "|".join(EVENT_FIELDS) + r"))\b")
EXPRESSION = re.compile(r"\$\{\{(.*?)\}\}")


def env_name(field: str) -> str:
    parts = [p for p in re.split(r"[.\[\]*]+", field) if p and not p.isdigit() and p not in {"github", "event"}]
    return "_".join(parts[-2:]).upper().replace("-", "_")


def check(wf: Workflow, config: Config) -> Iterator[Finding]:
    for _, step in wf.steps():
        for line, text in text_lines(step, "run"):
            for expr in EXPRESSION.finditer(text):
                if field := UNTRUSTED.search(expr[1]):
                    name = env_name(field[0])
                    yield wf.finding(
                        "WP006",
                        line,
                        f"`{expr[0]}` is attacker-controlled and is expanded into the script before the shell runs it; "
                        f'pass it through the environment instead: `env: {name}: ${{{{ {field[0]} }}}}` and use `"${name}"`',
                    )


RULE = Rule(
    "WP006",
    "No user-controlled `github.event` fields in `run:`",
    "`${{ }}` is substituted into the script text, so a crafted issue title or branch name becomes shell code.",
    check,
)
