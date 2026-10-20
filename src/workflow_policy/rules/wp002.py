from __future__ import annotations

from collections.abc import Iterator

from workflow_policy.config import Config
from workflow_policy.model import Finding, Rule, Workflow, key_line


def check(wf: Workflow, config: Config) -> Iterator[Finding]:
    allowed = ", ".join(sorted(config.write_scopes))
    for job_id, job in wf.jobs():
        perms = job.get("permissions")
        if perms == "write-all":
            yield wf.finding(
                "WP002",
                key_line(job, "permissions"),
                f"job `{job_id}` uses `permissions: write-all`; list only the scopes it needs",
            )
        elif isinstance(perms, dict):
            for scope, level in perms.items():
                if level == "write" and scope not in config.write_scopes:
                    yield wf.finding(
                        "WP002",
                        key_line(perms, scope),
                        f"job `{job_id}` requests `{scope}: write`, which is not in the write allowlist ({allowed})",
                    )


RULE = Rule(
    "WP002",
    "Job write scopes must come from the allowlist",
    "Every write scope widens what a compromised step can do, so writes are opt-in per job and reviewed centrally.",
    check,
)
