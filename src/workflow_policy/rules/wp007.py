from __future__ import annotations

import re
from collections.abc import Iterator

from workflow_policy.config import Config
from workflow_policy.model import Finding, Rule, Workflow, value_line

STARTS_AT_ZERO = re.compile(r"0+(?:$|[-/])")


def check(wf: Workflow, config: Config) -> Iterator[Finding]:
    schedule = wf.triggers().get("schedule")
    for entry in schedule if isinstance(schedule, list) else []:
        cron = entry.get("cron") if isinstance(entry, dict) else None
        if not isinstance(cron, str) or not cron.split():
            continue
        minute = cron.split()[0]
        if any(STARTS_AT_ZERO.match(part) for part in minute.split(",")):
            yield wf.finding(
                "WP007",
                value_line(entry, "cron"),
                f"cron `{cron.strip()}` fires at minute 0, GitHub's busiest moment, when scheduled runs are delayed "
                "or dropped; pick an off-peak minute such as 17",
            )


RULE = Rule(
    "WP007",
    "Schedules should avoid minute 0",
    "GitHub queues scheduled runs and sheds load at the top of the hour, so `0 * * * *` jobs run late or not at all.",
    check,
)
