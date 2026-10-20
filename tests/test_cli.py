import json
from pathlib import Path

import pytest

from workflow_policy.cli import main

CLEAN = "on: push\npermissions: {}\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make\n"
DIRTY = "on: push\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n"


def repo(tmp_path: Path, **workflows: str) -> Path:
    folder = tmp_path / ".github" / "workflows"
    folder.mkdir(parents=True)
    for name, body in workflows.items():
        (folder / f"{name}.yml").write_text(body, encoding="utf-8")
    return tmp_path


def test_clean_repo_exits_zero(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(repo(tmp_path, ci=CLEAN))
    assert main(["--format", "text"]) == 0
    assert capsys.readouterr().out.strip() == "workflow-policy: 1 workflow file(s) checked, no findings"


def test_findings_exit_one_with_text_output(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(repo(tmp_path, ci=DIRTY))
    assert main(["--format", "text"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith(".github/workflows/ci.yml:1: WP001 ")
    assert out[1].startswith(".github/workflows/ci.yml:6: WP004 ")
    assert out[-1] == "workflow-policy: 1 workflow file(s) checked, 2 finding(s)"


def test_auto_format_uses_annotations_on_actions(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(repo(tmp_path, ci=DIRTY))
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert main([]) == 1
    assert capsys.readouterr().out.startswith("::error file=.github/workflows/ci.yml,line=1,title=WP001 ")


def test_auto_format_is_text_locally(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(repo(tmp_path, ci=DIRTY))
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    main([])
    assert capsys.readouterr().out.startswith(".github/workflows/ci.yml:1:")


def test_writes_sarif(tmp_path, monkeypatch):
    monkeypatch.chdir(repo(tmp_path, ci=DIRTY))
    assert main(["--format", "text", "--sarif", "out/results.sarif"]) == 1
    doc = json.loads((tmp_path / "out" / "results.sarif").read_text(encoding="utf-8"))
    assert [r["ruleId"] for r in doc["runs"][0]["results"]] == ["WP001", "WP004"]


def test_root_outside_cwd_is_prefixed(tmp_path, capsys, monkeypatch):
    target = repo(tmp_path / "other", ci=DIRTY)
    monkeypatch.chdir(tmp_path)
    main(["--root", str(target), "--format", "text"])
    assert capsys.readouterr().out.startswith("other/.github/workflows/ci.yml:1:")


def test_unparseable_workflow_is_wp000(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(repo(tmp_path, broken="on: [push\n"))
    assert main(["--format", "text"]) == 1
    assert ".github/workflows/broken.yml:2: WP000 cannot parse YAML" in capsys.readouterr().out


def test_no_workflows_is_clean(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["--format", "text"]) == 0
    assert "0 workflow file(s) checked" in capsys.readouterr().out


def test_bad_format_is_usage_error():
    with pytest.raises(SystemExit) as exc:
        main(["--format", "xml"])
    assert exc.value.code == 2
