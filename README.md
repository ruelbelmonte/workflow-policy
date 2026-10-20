# workflow-policy

A GitHub Action that lints `.github/workflows/*.yml` for least-privilege permissions and
supply-chain hygiene. It fails CI with `file:line` errors that show up as annotations on the pull
request and, through SARIF, in code scanning.

The linter is static. It parses YAML with line numbers and makes no network calls. It cannot prove a
workflow safe; it catches the common, high-impact mistakes listed below.

## Usage

```yaml
name: workflow-policy
on:
  pull_request:
  push:
    branches: [main]

permissions: {}

jobs:
  lint:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write # only needed for the SARIF upload
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - id: policy
        uses: ruelbelmonte/workflow-policy@<sha> # v1
      - if: always()
        uses: github/codeql-action/upload-sarif@6f2ac81f5cd81fe351a197ba0b00d91d03cd2aee # v4.39.0
        with:
          sarif_file: ${{ steps.policy.outputs.sarif-file }}
          category: workflow-policy
```

Pin the action to the commit SHA of a release, as WP004 asks of every other action.

| Input | Default | Description |
|---|---|---|
| `path` | `.` | Repository root whose `.github/workflows` are checked. |
| `config` | `<path>/.github/workflow-policy.yml` | Policy file. Optional unless set explicitly. |
| `sarif-file` | `workflow-policy.sarif` | SARIF output path. Empty skips SARIF. |

| Output | Description |
|---|---|
| `sarif-file` | Path of the SARIF file, or empty. |

The action runs on Linux, macOS and Windows runners. It installs Python 3.12 with
`actions/setup-python` (without changing the job's own Python) and one dependency, `ruamel.yaml`,
from PyPI with `--require-hashes`.

To run it locally:

```sh
pip install ruamel.yaml==0.19.1
PYTHONPATH=src python -m workflow_policy --root path/to/repo [--sarif out.sarif] [--format text]
```

The exit code is `0` with no findings, `1` with findings, and `2` for usage errors.

## Rules

| ID | Rule | Rationale |
|---|---|---|
| [WP001](#wp001) | Top-level `permissions` must be declared and read-only | Without it every job inherits the repository's default token scopes, which may be write-all. |
| [WP002](#wp002) | Job write scopes must come from the allowlist | Every write scope widens what a compromised step can do. |
| [WP003](#wp003) | `id-token: write` only on jobs that use OIDC | An OIDC token lets any step impersonate the workflow to a cloud provider or signer. |
| [WP004](#wp004) | Third-party actions must be pinned to a commit SHA | Tags and branches are mutable, so the action's owner controls what your job runs. |
| [WP005](#wp005) | No PR head checkout under `pull_request_target` | That trigger has write tokens and secrets, so building fork code there hands both to the fork author. |
| [WP006](#wp006) | No user-controlled `github.event` fields in `run:` | `${{ }}` is substituted into the script text, so a crafted issue title becomes shell code. |
| [WP007](#wp007) | Schedules should avoid minute 0 | GitHub sheds scheduled load at the top of the hour, so those runs are delayed or dropped. |
| WP000 | Policy error | A workflow or the policy file could not be parsed, or an ignore is invalid or expired. Cannot be disabled. |

### WP001

Declare `permissions` at the top of every workflow, as `{}`, `read-all` or a map of `read`/`none`
scopes, and grant writes on the jobs that need them. Repositories created before February 2023,
and many organisations, still default the `GITHUB_TOKEN` to read-write. An undeclared workflow
silently gets those scopes. Files whose only trigger is `workflow_call` are exempt, because a
called workflow's token is capped by its caller.

### WP002

A job's `write` scopes must be on the allowlist: `contents`, `packages`, `id-token`,
`security-events`, `pull-requests` and `issues` by default. `permissions: write-all` on a job is
always reported. Scopes such as `actions: write` (edit workflow runs) or `deployments: write` are
rarely needed. When they are, add them to the allowlist in the policy file so the decision is
reviewed in one place.

### WP003

`id-token: write` lets the job mint an OIDC token. Only grant it to jobs with a step that exchanges
the token: `aws-actions/configure-aws-credentials`, `azure/login`, `google-github-actions/auth`,
`sigstore/cosign-installer`, `actions/attest`, `actions/attest-build-provenance` or
`actions/attest-sbom`. Jobs that call a reusable workflow are skipped, because the steps that use
the token live in the callee.

### WP004

Pin every action and reusable workflow to a full, lowercase, 40-character commit SHA, with the tag
as a comment: `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`. Pin
`docker://` images to a digest (`image@sha256:...`). Local actions (`./...`) are part of your
repository and are not checked. A tag can be moved to malicious code at any time, as in the
`tj-actions/changed-files` compromise of March 2025.

### WP005

`pull_request_target` runs in the context of the base repository, with secrets and a token that can
write. If it checks out the pull request's head, the contributor's code runs with both. The rule
reports:

- `actions/checkout` with a `ref` or `repository` taken from the PR (anything under
  `github.event.pull_request` except `base`, `github.head_ref`, `refs/pull/...`)
- `run:` steps that `gh pr checkout`, or that `git fetch`/`checkout`/`switch`/`pull`/`reset`/`merge`
  such a ref, including through `env:` variables and `$GITHUB_HEAD_REF`

Use `pull_request` for untrusted code. If you need privileges afterwards, add a separate
`workflow_run` workflow that never executes the PR's code.

### WP006

Expressions in `run:` are expanded before the shell sees the script, so
`echo "${{ github.event.issue.title }}"` runs whatever the issue title contains. The rule reports
attacker-controlled fields: titles and bodies of issues, PRs, discussions, comments and reviews;
commit messages and author names and emails; PR head ref, label and default branch; `github.head_ref`;
wiki page names; and `workflow_run` branch and commit fields. It also reports any enclosing object,
such as `toJSON(github.event)`. Matching is case-insensitive and understands `['x']`, `[0]` and `*`
syntax. Pass the value through the environment instead:

```yaml
- env:
    TITLE: ${{ github.event.issue.title }}
  run: echo "$TITLE"
```

### WP007

Scheduled workflows that fire at minute 0 (`0 * * * *`, `0,30 ...`, `0-10 ...`, `0/15 ...`) compete
with everyone else's top-of-the-hour jobs. GitHub documents that such runs may be delayed, and under
high load dropped. Pick an off-peak minute such as 17. `*` and `*/N` are not reported.

## Configuration

An optional `.github/workflow-policy.yml`:

```yaml
disable: [WP007]              # rule IDs to turn off

write-scopes: [deployments]   # added to the WP002 default allowlist

ignore:
  - path: .github/workflows/legacy-*.yml   # glob, relative to the repository root
    rules: [WP004]                          # required: the rules this entry suppresses
    reason: vendor action publishes no releases; tracked in #42
    expires: 2026-12-31                     # required, YYYY-MM-DD
```

Every `ignore` entry needs `path`, `rules`, `reason` and `expires`. From the day after `expires`, the
entry stops suppressing anything and reports a WP000 error until it is fixed or renewed. A typo,
an unknown key or an unknown rule ID is also WP000, so a broken policy cannot quietly turn
checks off.

## Development

```sh
uv venv -p 3.12 && uv pip install --require-hashes -r requirements-dev.txt
.venv/bin/python -m pytest   # enforces 90% branch coverage
```

Each rule has fixtures under `tests/fixtures/<rule>/`. Files in `good/` must produce no findings.
In `bad/`, each line marked `# expect: WPnnn` must produce exactly one finding.

This repository runs the action on its own workflows in CI and follows every rule.

### Releasing

Bump `__version__` in `src/workflow_policy/__init__.py` and merge to `master`. Then run the
**release** workflow with that version. It runs the tests, creates the `vX.Y.Z` tag, moves the `vX`
tag to it, and publishes a GitHub release. Marketplace listing is a manual step on the release page.

## Licence

[MIT](LICENSE)
