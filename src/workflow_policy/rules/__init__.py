from workflow_policy.model import Rule
from workflow_policy.rules import wp001, wp002, wp003, wp004, wp005, wp006, wp007

RULES: dict[str, Rule] = {
    m.RULE.id: m.RULE for m in (wp001, wp002, wp003, wp004, wp005, wp006, wp007)
}
