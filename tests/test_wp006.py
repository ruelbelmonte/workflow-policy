from helpers import FIXTURES, findings


def test_message_suggests_env_var_pattern():
    first = findings("WP006", FIXTURES / "wp006" / "bad" / "injection.yml")[0]
    assert "`${{ github.event.issue.title }}`" in first.message
    assert "ISSUE_TITLE: ${{ github.event.issue.title }}" in first.message
    assert '"$ISSUE_TITLE"' in first.message
