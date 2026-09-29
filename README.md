# PS5 Homebrew Catalog

A small public catalog of BlackBearReloaded's titled PS5 homebrew. The current entries are `PPSA99001` through `PPSA99008`.

Each `apps/PPSAxxxxx.json` file contains exactly ten fields: `titleid`, `name`, `kind`, `description`, `license`, `author`, `version`, `source_repo`, `artifact_url`, and `icon_url`. Artifact URLs point directly to versioned ZIP assets in the publisher's GitHub Releases. Icon URLs point directly to image files.

Validate changes with:

```sh
python3 scripts/validate.py
```

The same check runs on pull requests and pushes to `main`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the entry format.
