# Artifact formats

A listed artifact is a single release asset in one of these formats:

| Extension | Contents |
| --- | --- |
| `.zip` | The app folder (`<TITLEID>/` with `eboot.bin` and `sce_sys/`), to be extracted to `/data/homebrew/` |
| `.ffpfsc` | Compressed PFS image of the app |
| `.ffpkg` | Fake-signed package of the app |

Loaders such as [ShadowMountPlus](https://github.com/drakmor/ShadowMountPlus)
can use all three.

## What the catalog verifies

Only that the file at `artifact_url` is byte-for-byte the file the record's
`sha256` describes, and that it is at most 2 GiB (GitHub's asset limit). The
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
