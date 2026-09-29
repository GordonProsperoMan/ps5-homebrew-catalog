# Contributing

Add or update one JSON file in `apps/`, named `<titleid>.json` (for example, `PPSA99001.json`). Keep only these fields:

```json
{
  "titleid": "PPSA99001",
  "name": "App name",
  "kind": "app",
  "description": "One short sentence.",
  "license": "GPL-3.0",
  "author": "Publisher name",
  "version": "01.000.005",
  "source_repo": "https://github.com/publisher/project",
  "artifact_url": "https://github.com/publisher/project/releases/download/01.000.005/PPSA99001.zip",
  "icon_url": "https://raw.githubusercontent.com/publisher/project/01.000.005/sce_sys/icon0.png"
}
```

Use the exact, versioned ZIP asset URL from the publisher's GitHub Release. Provide a direct HTTPS link to the app's PNG, JPEG, or WebP icon; a release tag or commit URL keeps the image stable. Current `kind` values are `app`, `game`, and `tool`. Run `python3 scripts/validate.py` before submitting a change.
