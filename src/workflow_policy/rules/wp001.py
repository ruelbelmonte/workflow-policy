from __future__ import annotations

from collections.abc import Iterator

from workflow_policy.config import Config
from workflow_policy.model import Finding, Rule, Workflow, key_line

READ_ONLY = {"read", "none"}


def check(wf: Workflow, config: Config) -> Iterator[Finding]:
    if set(wf.triggers()) == {"workflow_call"}:
        return
    data = wf.data
    if "permissions" not in data:
        yield wf.finding(
            "WP001", 1, "no top-level `permissions`; add `permissions: {}` (or `contents: read`) and grant writes per job"
        )
        return
    perms = data["permissions"]
    if perms == "read-all":
        return
    if isinstance(perms, dict):
        for scope, level in perms.items():
            if level not in READ_ONLY:
                yield wf.finding(
                    "WP001",
                    key_line(perms, scope),
                    f"top-level `{scope}: {level}` grants every job write access; set it to `read` and grant it on the job that needs it",
                )
        return
    yield wf.finding(
        "WP001",
        key_line(data, "permissions"),
        f"top-level `permissions: {perms or ''}` is not read-only; use `{{}}`, `read-all` or a map of `read`/`none` scopes",
    )


RULE = Rule(
    "WP001",
    "Top-level permissions must be declared and read-only",
    "Without a top-level block every job inherits the repository's default token scopes, which may be write-all.",
    check,
)
