# Contributing

Add or update one file under `apps/` using the [JSON metadata format](README.md#json-metadata-format). Name it `<titleid>.json`, for example `PPSA99001.json`.

Publish the ZIP in your project's GitHub Releases and use its exact, version-specific asset URL. Provide a direct HTTPS link to your app's icon image, preferably pinned to a release tag or commit. Run `python3 scripts/validate.py` before submitting a change.
