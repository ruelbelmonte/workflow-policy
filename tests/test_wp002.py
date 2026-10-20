from helpers import FIXTURES, findings, lines
from workflow_policy.config import DEFAULT_WRITE_SCOPES, Config

BAD = FIXTURES / "wp002" / "bad" / "disallowed_scopes.yml"


def test_allowlist_can_be_extended():
    config = Config(write_scopes=DEFAULT_WRITE_SCOPES | {"deployments", "statuses"})
    assert lines("WP002", BAD, config) == [10]


def test_message_names_job_and_scope():
    first = findings("WP002", BAD)[0]
    assert "`deployments: write`" in first.message and "`deploy`" in first.message
