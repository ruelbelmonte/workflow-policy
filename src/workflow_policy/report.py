from __future__ import annotations

from workflow_policy import __version__
from workflow_policy.model import Finding
from workflow_policy.rules import RULES

REPO_URL = "https://github.com/ruelbelmonte/workflow-policy"
POLICY_ERROR = ("WP000", "Policy error", "The workflow or policy file could not be checked as written.")


def _titles() -> dict[str, str]:
    return {POLICY_ERROR[0]: POLICY_ERROR[1], **{r.id: r.title for r in RULES.values()}}


def _data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _property(value: str) -> str:
    return _data(value).replace(":", "%3A").replace(",", "%2C")


def annotation(f: Finding) -> str:
    title = f"{f.rule} {_titles()[f.rule]}"
    return f"::error file={_property(f.path)},line={f.line},title={_property(title)}::{_data(f.message)}"


def text(f: Finding) -> str:
    return f"{f.path}:{f.line}: {f.rule} {f.message}"


def sarif(findings: list[Finding]) -> dict:
    rules = [POLICY_ERROR] + [(r.id, r.title, r.rationale) for _, r in sorted(RULES.items())]
    index = {rule_id: i for i, (rule_id, _, _) in enumerate(rules)}
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "workflow-policy",
                        "version": __version__,
                        "informationUri": REPO_URL,
                        "rules": [
                            {
                                "id": rule_id,
                                "name": rule_id,
                                "shortDescription": {"text": title},
                                "fullDescription": {"text": rationale},
                                "helpUri": f"{REPO_URL}#{rule_id.lower()}",
                                "defaultConfiguration": {"level": "error"},
                                "properties": {"tags": ["security", "github-actions"]},
                            }
                            for rule_id, title, rationale in rules
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": f.rule,
                        "ruleIndex": index[f.rule],
                        "level": "error",
                        "message": {"text": f.message},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": f.path, "uriBaseId": "%SRCROOT%"},
                                    "region": {"startLine": f.line},
                                }
                            }
                        ],
                    }
                    for f in findings
                ],
            }
        ],
    }
