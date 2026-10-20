from __future__ import annotations

import re
from collections.abc import Iterator

from ruamel.yaml.comments import CommentedMap

from workflow_policy.config import Config
from workflow_policy.model import (
    Finding,
    Rule,
    Workflow,
    action_name,
    normalize_expression,
    text_lines,
    value_line,
)

# Everything on the pull request except the base describes the contributor's code.
PR_HEAD = re.compile(r"github\.head_ref|github\.event\.number|github\.event\.pull_request\.(?!base\.)|refs/pull/|\bpull/")
GH_CHECKOUT = re.compile(r"\bgh\b.*\bpr\s+checkout\b")
GIT_FETCH = re.compile(r"\bgit\b.*\b(fetch|checkout|switch|pull|reset|merge|worktree)\b")
MESSAGE = (
    "`pull_request_target` runs with a privileged token and secrets; checking out the PR head runs untrusted code "
    "with them. Use `pull_request`, or split into an unprivileged `pull_request` job plus a `workflow_run` follow-up"
)


def is_pr_head(text: str) -> bool:
    return bool(PR_HEAD.search(normalize_expression(text)))


def tainted_env(*scopes: object) -> set[str]:
    return {
        name.lower()
        for env in scopes
        if isinstance(env, dict)
        for name, value in env.items()
        if isinstance(value, str) and is_pr_head(value)
    }


def logical_lines(step: CommentedMap) -> Iterator[tuple[int, str]]:
    start, buf = 0, ""
    for line, text in text_lines(step, "run"):
        start, buf = (start, buf + " " + text) if buf else (line, text)
        if buf.rstrip().endswith("\\"):
            buf = buf.rstrip()[:-1]
            continue
        yield start, buf
        buf = ""
    if buf:
        yield start, buf


def checks_out_head(text: str, env: set[str]) -> bool:
    norm = normalize_expression(text)
    if GH_CHECKOUT.search(norm):
        return True
    if not GIT_FETCH.search(norm):
        return False
    refs_env = any(re.search(rf"\$\{{?{re.escape(n)}\b|\benv\.{re.escape(n)}\b", norm) for n in env)
    return refs_env or bool(PR_HEAD.search(norm))


def check(wf: Workflow, config: Config) -> Iterator[Finding]:
    if "pull_request_target" not in wf.triggers():
        return
    for job_id, job in wf.jobs():
        steps = job.get("steps")
        for step in steps if isinstance(steps, list) else []:
            if not isinstance(step, CommentedMap):
                continue
            uses, with_ = step.get("uses"), step.get("with")
            if isinstance(uses, str) and action_name(uses) == "actions/checkout" and isinstance(with_, dict):
                for key in ("ref", "repository"):
                    if isinstance(with_.get(key), str) and is_pr_head(with_[key]):
                        yield wf.finding("WP005", value_line(with_, key), MESSAGE)
            env = tainted_env(wf.data.get("env"), job.get("env"), step.get("env"))
            for line, text in logical_lines(step):
                if checks_out_head(text, env):
                    yield wf.finding("WP005", line, MESSAGE)


RULE = Rule(
    "WP005",
    "No PR head checkout under `pull_request_target`",
    "`pull_request_target` has write tokens and secrets, so building fork code there hands both to the fork author.",
    check,
)
