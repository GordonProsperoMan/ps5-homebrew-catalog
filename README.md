# PS5 Homebrew Catalog

A small public catalog of BlackBearReloaded's titled PS5 homebrew. The current entries are `PPSA99001` through `PPSA99008`.

The metadata in this repository is used to dynamically update the [PS5 homebrew website](https://homebrew.page/ps5/).

## JSON metadata format

Add one file at `apps/<titleid>.json`; its filename must match the `titleid` value. Each file is a single JSON object with **exactly** these ten string fields:

```json
{
  "titleid": "PPSA99001",
  "name": "App name",
  "kind": "app",
  "description": "One short sentence about the app.",
  "license": "GPL-3.0",
  "author": "Publisher name",
  "version": "1.0.0",
  "source_repo": "https://github.com/publisher/project",
  "artifact_url": "https://github.com/publisher/project/releases/download/v1.0.0/PPSA99001.zip",
  "icon_url": "https://raw.githubusercontent.com/publisher/project/v1.0.0/sce_sys/icon0.png"
}
```

| Field | Expected value |
| --- | --- |
| `titleid` | PS5 title ID in the current `PPSA99001`–`PPSA99009` range; must match the filename. |
| `name` | App's display name. |
| `kind` | `app`, `game`, or `tool`. |
| `description` | Short plain-text description. |
| `license` | Project's license identifier, such as `GPL-3.0`. |
| `author` | Developer or publisher name. |
| `version` | Version displayed in the catalog. |
| `source_repo` | HTTPS URL of the project's GitHub repository. |
| `artifact_url` | Direct, version-specific `.zip` asset URL from that repository's GitHub Releases. |
| `icon_url` | Direct HTTPS link to a PNG, JPEG, or WebP image; use a release tag or commit to keep it stable. |

The validator rejects missing or extra fields, duplicate JSON keys, empty strings, values over 500 characters, and files over 8 KiB. It checks URL format but does not download the artifact or icon.

Validate changes with:

```sh
python3 scripts/validate.py
```

The same check runs on pull requests and pushes to `main`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the submission workflow.
