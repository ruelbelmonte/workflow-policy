from __future__ import annotations

import re
from collections.abc import Iterator

from ruamel.yaml.comments import CommentedMap

from workflow_policy.config import Config
from workflow_policy.model import (
    EXPRESSION,
    Finding,
    Rule,
    Script,
    Workflow,
    action_name,
    normalize_expression,
    script,
    value_line,
)

# Everything on the pull request except the base describes the contributor's code.
PR_HEAD = re.compile(
    r"github\.head_ref|\bgithub_head_ref\b|github\.event\.number|github\.event\.pull_request\.(?!base\.)|refs/pull/|\bpull/"
)
GH_CHECKOUT = re.compile(r"\bgh\b.*\bpr\s+checkout\b")
GIT_FETCH = re.compile(r"\bgit\b.*\b(fetch|checkout|switch|pull|reset|merge|worktree)\b")
MESSAGE = (
    "`pull_request_target` runs with a privileged token and secrets; checking out the PR head runs untrusted code "
    "with them. Use `pull_request`, or split into an unprivileged `pull_request` job plus a `workflow_run` follow-up"
)


def mentions_head(text: str, env: set[str]) -> bool:
    norm = normalize_expression(text)
    if PR_HEAD.search(norm):
        return True
    return any(re.search(rf"\$\{{?{re.escape(n)}\b|\benv\.{re.escape(n)}\b", norm) for n in env)


def tainted_env(*scopes: object) -> set[str]:
    """Env names carrying head data, followed through chains such as `B: ${{ env.A }}`."""
    entries = [(n.lower(), v) for env in scopes if isinstance(env, dict) for n, v in env.items() if isinstance(v, str)]
    tainted: set[str] = set()
    while new := {name for name, value in entries if name not in tainted and mentions_head(value, tainted)}:
        tainted |= new
    return tainted


def commands(run: Script) -> Iterator[tuple[int, str]]:
    """Yield (offset, command) over the text the runner sees, joining `\\` continuations and `${{ }}` spans."""
    start, pos, buf = 0, 0, ""
    for raw in run.text.split("\n"):
        if not buf:
            start = pos
        pos += len(raw) + 1
        buf = f"{buf} {raw}" if buf else raw
        if buf.rstrip().endswith("\\"):
            buf = buf.rstrip()[:-1]
            continue
        if "${{" in EXPRESSION.sub("", buf):
            continue
        yield start, buf
        buf = ""
    if buf:
        yield start, buf


def checks_out_head(text: str, env: set[str]) -> bool:
    norm = normalize_expression(text)
    return bool(GH_CHECKOUT.search(norm)) or bool(GIT_FETCH.search(norm) and mentions_head(text, env))


def check(wf: Workflow, config: Config) -> Iterator[Finding]:
    if "pull_request_target" not in wf.triggers():
        return
    for _, job in wf.jobs():
        steps = job.get("steps")
        for step in steps if isinstance(steps, list) else []:
            if not isinstance(step, CommentedMap):
                continue
            env = tainted_env(wf.data.get("env"), job.get("env"), step.get("env"))
            uses, with_ = step.get("uses"), step.get("with")
            if isinstance(uses, str) and action_name(uses) == "actions/checkout" and isinstance(with_, dict):
                for key in ("ref", "repository"):
                    if isinstance(with_.get(key), str) and mentions_head(with_[key], env):
                        yield wf.finding("WP005", value_line(with_, key), MESSAGE)
            if run := script(step, "run"):
                for offset, text in commands(run):
                    if checks_out_head(text, env):
                        yield wf.finding("WP005", run.line_at(offset), MESSAGE)


RULE = Rule(
    "WP005",
    "No PR head checkout under `pull_request_target`",
    "`pull_request_target` has write tokens and secrets, so building fork code there hands both to the fork author.",
    check,
)
