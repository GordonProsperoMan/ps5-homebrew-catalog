# Artifact formats

A listed artifact is a single release asset in one of these formats:

| Extension | Contents | Where it goes |
| --- | --- | --- |
| `.zip` | The app folder `<TITLEID>/` (with `eboot.bin` and `sce_sys/`) | Extract, then copy the folder to `/data/homebrew/` |
| `.ffpkg` | UFS2 image with `sce_sys/param.json` at its root | Copy the file to `/data/homebrew/` |
| `.ffpfsc` | Compressed PFS container holding a nested image | Copy the file to `/data/homebrew/` |

[ShadowMountPlus](https://github.com/drakmor/ShadowMountPlus) scans
`/data/homebrew/` and mounts all three; it recommends `.ffpkg` for images.

## What the catalog verifies

Only that the file at `artifact_url` is byte-for-byte the file the record's
`sha256` describes, and that it is at most 2 GiB (GitHub's asset limit). The
check uses the SHA-256 digest GitHub computes for every release asset, so the
catalog never downloads artifacts. The
catalog doesn't open, inspect or run artifacts, so it doesn't vouch for their
contents or that they work; that responsibility stays with the developer and
the maintainer review.

## Recommendations

- Name the asset after the title ID, e.g. `PPSA01234.zip`.
- Use the same title ID as `titleId` in `sce_sys/param.json`, and keep the
  title ID, `conceptId` and `contentId` stable across releases so updates keep
  the app's data.
- Keep user data out of the app itself, in writable locations such as
  `/download0`, which survive replacing the app.
- Never replace an asset that is already listed; publish a new release instead.
