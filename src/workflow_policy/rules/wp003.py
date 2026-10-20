from __future__ import annotations

from collections.abc import Iterator

from workflow_policy.config import Config
from workflow_policy.model import Finding, Rule, Workflow, action_name, key_line

OIDC_ACTIONS = frozenset(
    {
        "aws-actions/configure-aws-credentials",
        "azure/login",
        "google-github-actions/auth",
        "sigstore/cosign-installer",
        "actions/attest",
        "actions/attest-build-provenance",
        "actions/attest-sbom",
    }
)


def check(wf: Workflow, config: Config) -> Iterator[Finding]:
    for job_id, job in wf.jobs():
        perms = job.get("permissions")
        if not isinstance(perms, dict) or perms.get("id-token") != "write":
            continue
        # A reusable-workflow job passes the token to a callee this file can't see.
        if "uses" in job:
            continue
        steps = job.get("steps") or []
        used = {action_name(s["uses"]) for s in steps if isinstance(s, dict) and isinstance(s.get("uses"), str)}
        if not used & OIDC_ACTIONS:
            yield wf.finding(
                "WP003",
                key_line(perms, "id-token"),
                f"job `{job_id}` grants `id-token: write` but no step assumes a cloud role or signs; remove it",
            )


RULE = Rule(
    "WP003",
    "`id-token: write` only on jobs that use OIDC",
    "An OIDC token lets any step in the job impersonate the workflow to a cloud provider or signing service.",
    check,
)
