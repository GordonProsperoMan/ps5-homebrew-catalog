# Automation

All checks are implemented in [`catalog/`](../catalog) with the Python standard
library and run by three workflows.

| Workflow | Trigger | Runs |
| --- | --- | --- |
| [Submission check](../.github/workflows/pull-request.yml) | Pull requests (`pull_request_target`) | `python3 -m catalog pr` |
| [CI](../.github/workflows/ci.yml) | Pull requests and pushes to `main` | Tests and `catalog check`; on `main` also `catalog push` |
| [Catalog health](../.github/workflows/health.yml) | Mondays 06:17 UTC and manual | `catalog health` |

Results appear as annotations and in each run's job summary.

## Submission check

For a pull request the checker:

1. **Classifies the changed files.** Community pull requests may only add or
   modify exactly one `apps/<TITLEID>.json`, as a regular, non-executable file.
   Deletions and changes to any other file are reserved for maintainers
   (`OWNER`, `MEMBER` or `COLLABORATOR` of this repository).
2. **Validates the merged catalog.** It applies the PR's records on top of the
   current `main` and checks every record's format plus catalog-wide uniqueness
   of names, artifact URLs and digests. See [Metadata format](metadata.md).
3. **Confirms the publisher.** The PR author must own `source_repo`, or be a
   public member of the organization that owns it. A record's title ID can't be
   moved to a different repository owner by a community PR.
4. **Verifies the release.** Through the GitHub API: the repository is public
   and the URL is canonical, the license agrees with GitHub's detection, the tag
   is a published release, the asset exists and is at most 1 GiB, and GitHub's
   own asset digest equals `sha256`.
5. **Verifies the bytes.** It streams the artifact to a temporary file, hashes
   it, and requires the hash to equal `sha256`. It then inspects the ZIP against
   [`homebrew-zip-v1`](package-format.md), decompressing each file in memory to
   check CRCs and real sizes, and reads `sce_sys/param.json`.
6. **Checks the icon.** It fetches at most 2 MiB and requires PNG, JPEG or WebP
   content, warning when a PNG isn't square or is under 256×256.

### Why it is safe on untrusted pull requests

The workflow uses `pull_request_target`, so it runs the **base branch's**
workflow and checker, never the pull request's. It checks out `main`, fetches the
PR head as a git ref, and reads the changed records with `git show` as plain
data. PR code is never checked out or executed, so a submission can't alter the
rules it is judged by. The token is read-only, no secrets are used, artifacts
are never extracted to disk or executed, and every download and decompression
is size-bounded. Actions are pinned to commit SHAs and kept current by
Dependabot.

The CI workflow does run PR code (tests), with the standard read-only
`pull_request` token and no secrets.

## Push to `main`

Every push runs the tests and the offline check, then fully verifies the records
changed since the previous commit. This covers maintainer commits that don't go
through a pull request.

## Weekly health check

Re-verifies every record end to end (release, digest, download, package, icon)
and reports projects that have published a newer release than the one listed.
A failure notifies maintainers; see the [review policy](review-policy.md) for
how broken listings are handled.

## Recommended repository settings

Maintainers should protect `main` with a ruleset for pull requests that:

- requires the **Validate submission** and **Tests and offline check** status
  checks to pass,
- requires one approving review, and
- blocks force pushes and deletion.

Maintainers can keep a bypass for direct pushes, which are still verified by the
push workflow.

## Running checks locally

```sh
python3 -m catalog check                   # offline format check of apps/
python3 -m catalog verify [TITLEID ...]    # online checks for some or all records
python3 -m catalog verify --no-download    # skip artifact download and ZIP checks
python3 -m catalog digest <artifact_url>   # sha256 as reported by GitHub
python3 -m catalog health                  # what the weekly job runs
python3 -m unittest discover -s tests
```

Set `GITHUB_TOKEN` (for example `GITHUB_TOKEN=$(gh auth token)`) to avoid the
anonymous API limit of 60 requests per hour.
