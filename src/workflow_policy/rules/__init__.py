from workflow_policy.model import Rule
from workflow_policy.rules import wp001, wp002, wp003, wp004, wp005, wp006, wp007

RULES: dict[str, Rule] = {rule.id: rule for rule in (wp001.RULE, wp002.RULE, wp003.RULE, wp004.RULE, wp005.RULE, wp006.RULE, wp007.RULE)}
