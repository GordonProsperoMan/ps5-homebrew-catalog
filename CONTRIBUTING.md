# Contributing catalog entries

Add one YAML file under `apps/`, named after the suffix of its stable catalog `id`. Use an existing file as the format example. Include a project repository, license, short description, and categories. An app or game also needs its title ID, an icon, and a release block for one exact ZIP asset.

Publish the artifact in your project's GitHub Releases before opening the PR. Link to a **version-specific** ZIP asset, not `latest`. Supply its byte size, SHA-256, uncompressed size, and single archive root. A valid app ZIP currently has a title ID root containing `eboot.bin`, `sce_sys/param.json`, and `sce_sys/icon0.png`. Calculate the hash with `sha256sum your-app.zip`; obtain the compressed byte size with `stat -c %s your-app.zip`. The catalog icon should be the PNG from the release, copied to `assets/icons/<title_id>.png`.

Set `release.sequence: 1` for a new entry and increase it for every subsequent artifact, even if the display version remains the same. Use `channel: alpha` for preview releases. Keep `installation_verified: false` until the supported PS5 loader, firmware, archive handling, and update behavior are tested on hardware. For a non-app project, omit title ID, icon, and release artifact fields; a release page link is optional.

Run `python3 scripts/validate.py` before opening the PR. Maintainers also check project ownership, release provenance, the asset hash, and archive layout. The validator does not execute downloaded software or certify that it is safe.
