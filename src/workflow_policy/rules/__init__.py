from workflow_policy.model import Rule
from workflow_policy.rules import wp001

RULES: dict[str, Rule] = {rule.id: rule for rule in (wp001.RULE,)}
