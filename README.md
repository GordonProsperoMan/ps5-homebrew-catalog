# PS5 Homebrew Catalog

A small public catalog of BlackBearReloaded's titled PS5 homebrew. The current entries are `PPSA99001` through `PPSA99008`.

Each `apps/PPSAxxxxx.json` file contains exactly nine fields: `titleid`, `name`, `kind`, `description`, `license`, `author`, `version`, `source_repo`, and `artifact_url`. Artifact URLs point directly to versioned ZIP assets in the publisher's GitHub Releases.

Validate changes with:

```sh
python3 scripts/validate.py
```

The same check runs on pull requests and pushes to `main`. See [CONTRIBUTING.md](CONTRIBUTING.md) for the entry format.
