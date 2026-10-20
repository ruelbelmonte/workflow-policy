from helpers import lines


def test_backslash_continuation_reports_first_line(tmp_path):
    wf = tmp_path / "wf.yml"
    wf.write_text(
        "on: pull_request_target\n"
        "jobs:\n"
        "  t:\n"
        "    steps:\n"
        "      - run: |\n"
        "          git fetch \\\n"
        "            origin ${{ github.event.pull_request.head.sha }}\n"
        "          make\n",
        encoding="utf-8",
    )
    assert lines("WP005", wf) == [6]


def test_folded_scalar_and_multiline_expression(tmp_path):
    wf = tmp_path / "wf.yml"
    wf.write_text(
        "on: pull_request_target\n"
        "jobs:\n"
        "  t:\n"
        "    steps:\n"
        "      - run: >\n"
        "          git fetch origin\n"
        "          ${{ github.event.pull_request.head.sha }}\n"
        "      - run: |\n"
        "          git checkout ${{\n"
        "            github.event.pull_request.head.sha }}\n",
        encoding="utf-8",
    )
    assert lines("WP005", wf) == [6, 9]


def test_string_literal_braces_do_not_end_expression_early(tmp_path):
    wf = tmp_path / "wf.yml"
    wf.write_text(
        "on: pull_request_target\n"
        "jobs:\n"
        "  t:\n"
        "    steps:\n"
        "      - run: |\n"
        "          git checkout ${{ format('}}{0}',\n"
        "            github.event.pull_request.head.sha) }}\n",
        encoding="utf-8",
    )
    assert lines("WP005", wf) == [6]
