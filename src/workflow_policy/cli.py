from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from workflow_policy import __version__
from workflow_policy.engine import lint, workflow_files
from workflow_policy.report import annotation, sarif, text


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="workflow-policy",
        description="Lint .github/workflows for least-privilege and supply-chain hygiene.",
    )
    parser.add_argument("--root", type=Path, default=Path("."), help="repository root (default: .)")
    parser.add_argument("--config", type=Path, help="policy file (default: <root>/.github/workflow-policy.yml)")
    parser.add_argument("--sarif", type=Path, help="also write SARIF 2.1.0 results to this file")
    parser.add_argument(
        "--format",
        choices=["auto", "github", "text"],
        default="auto",
        help="github annotations or plain text; auto picks github inside GitHub Actions",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    findings = lint(args.root, args.config)

    github = args.format == "github" or (args.format == "auto" and os.environ.get("GITHUB_ACTIONS") == "true")
    for finding in findings:
        print(annotation(finding) if github else text(finding))

    if args.sarif:
        args.sarif.parent.mkdir(parents=True, exist_ok=True)
        args.sarif.write_text(json.dumps(sarif(findings), indent=2) + "\n", encoding="utf-8")

    checked = len(workflow_files(args.root))
    result = f"{len(findings)} finding(s)" if findings else "no findings"
    print(f"workflow-policy: {checked} workflow file(s) checked, {result}")
    return 1 if findings else 0
