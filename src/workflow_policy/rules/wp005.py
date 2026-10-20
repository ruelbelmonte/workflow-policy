from __future__ import annotations

import re
from collections.abc import Iterator

from workflow_policy.config import Config
from workflow_policy.model import Finding, Rule, Workflow, action_name, text_lines, value_line

PR_HEAD = re.compile(
    r"github\.event\.pull_request\.head\.(sha|ref|repo\.full_name)|github\.head_ref|refs/pull/"
)
SHELL_CHECKOUT = re.compile(r"\bgh\s+pr\s+checkout\b|\bgit\s+(fetch|checkout|switch|pull)\b.*(pull/|" + PR_HEAD.pattern + ")")
MESSAGE = (
    "`pull_request_target` runs with a privileged token and secrets; checking out the PR head runs untrusted code "
    "with them. Use `pull_request`, or split into an unprivileged `pull_request` job plus a `workflow_run` follow-up"
)


def check(wf: Workflow, config: Config) -> Iterator[Finding]:
    if "pull_request_target" not in wf.triggers():
        return
    for _, step in wf.steps():
        uses, with_ = step.get("uses"), step.get("with")
        if isinstance(uses, str) and action_name(uses) == "actions/checkout" and isinstance(with_, dict):
            for key in ("ref", "repository"):
                if isinstance(with_.get(key), str) and PR_HEAD.search(with_[key]):
                    yield wf.finding("WP005", value_line(with_, key), MESSAGE)
        for line, text in text_lines(step, "run"):
            if SHELL_CHECKOUT.search(text):
                yield wf.finding("WP005", line, MESSAGE)


RULE = Rule(
    "WP005",
    "No PR head checkout under `pull_request_target`",
    "`pull_request_target` has write tokens and secrets, so building fork code there hands both to the fork author.",
    check,
)
