from helpers import FIXTURES, findings, lines


def test_message_suggests_env_var_pattern():
    first = findings("WP006", FIXTURES / "wp006" / "bad" / "injection.yml")[0]
    assert "`${{ github.event.issue.title }}`" in first.message
    assert "ISSUE_TITLE: ${{ github.event.issue.title }}" in first.message
    assert '"$ISSUE_TITLE"' in first.message


def test_expression_spanning_lines_reports_its_first_line(tmp_path):
    wf = tmp_path / "wf.yml"
    wf.write_text(
        "on: issues\n"
        "jobs:\n"
        "  t:\n"
        "    steps:\n"
        "      - run: |\n"
        "          echo ok\n"
        '          echo "${{\n'
        '            github.event.issue.body }}"\n',
        encoding="utf-8",
    )
    assert lines("WP006", wf) == [7]


def test_folded_scalar_matches_text_runner_sees(tmp_path):
    wf = tmp_path / "wf.yml"
    wf.write_text(
        "on: issues\n"
        "jobs:\n"
        "  t:\n"
        "    steps:\n"
        "      - run: >\n"
        "          echo first\n"
        '          "${{ github.event.issue.title\n'
        '          }}"\n',
        encoding="utf-8",
    )
    assert lines("WP006", wf) == [7]
