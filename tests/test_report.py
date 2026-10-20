from workflow_policy import __version__
from workflow_policy.model import Finding
from workflow_policy.report import annotation, sarif, text
from workflow_policy.rules import RULES

FINDING = Finding(".github/workflows/ci,1.yml", 8, "WP004", "`a@v1` is not pinned: 100%\nreally")


def test_annotation_escapes_data_and_properties():
    assert annotation(FINDING) == (
        "::error file=.github/workflows/ci%2C1.yml,line=8,"
        "title=WP004 Third-party actions must be pinned to a commit SHA"
        "::`a@v1` is not pinned: 100%25%0Areally"
    )


def test_text_is_file_line_located():
    assert text(FINDING).startswith(".github/workflows/ci,1.yml:8: WP004 ")


def test_policy_error_annotation_has_title():
    assert "title=WP000 Policy error" in annotation(Finding("p.yml", 2, "WP000", "bad"))


def test_sarif_document():
    doc = sarif([FINDING, Finding("p.yml", 1, "WP000", "bad")])
    assert doc["version"] == "2.1.0"
    (run,) = doc["runs"]
    driver = run["tool"]["driver"]
    assert driver["name"] == "workflow-policy" and driver["version"] == __version__
    ids = [r["id"] for r in driver["rules"]]
    assert ids == ["WP000", *sorted(RULES)]
    first = run["results"][0]
    assert first["ruleId"] == "WP004" and ids[first["ruleIndex"]] == "WP004"
    assert first["level"] == "error"
    location = first["locations"][0]["physicalLocation"]
    assert location == {
        "artifactLocation": {"uri": ".github/workflows/ci,1.yml", "uriBaseId": "%SRCROOT%"},
        "region": {"startLine": 8},
    }
    assert all(r["fullDescription"]["text"] and r["helpUri"].endswith(r["id"].lower()) for r in driver["rules"])


def test_empty_sarif_still_lists_rules():
    run = sarif([])["runs"][0]
    assert run["results"] == [] and len(run["tool"]["driver"]["rules"]) == len(RULES) + 1


def test_text_cannot_smuggle_workflow_commands():
    out = text(Finding("ci.yml", 3, "WP004", "`x@v1\n::add-mask::secret\r`"))
    assert "\n" not in out and "\r" not in out
    assert out.endswith(r"`x@v1\n::add-mask::secret\r`")
