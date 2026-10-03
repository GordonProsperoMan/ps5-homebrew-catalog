# Artifact formats

**The catalog currently accepts one format: a `.zip` of the app folder.** New
listings, and new releases of listed apps, must be a `.zip`.

| Extension | Contents | Where it goes |
| --- | --- | --- |
| `.zip` | The app folder `<TITLEID>/` (with `eboot.bin` and `sce_sys/`) at the top of the archive | Extract, then copy the folder to `/data/homebrew/` |

[ShadowMountPlus](https://github.com/drakmor/ShadowMountPlus) scans
`/data/homebrew/` and registers the folder.

## Why only ZIP

The catalog feeds ProsperoStore, the console app store being built on the
[store API](api.md). It installs, updates and removes apps as folders, and a
`.zip` of the app folder is the one format it is designed to handle. One
format also means one set of install steps on the website.

## Image formats (`.ffpkg`, `.ffpfsc`)

Image files (`.ffpkg`, a UFS2 image; `.ffpfsc`, a compressed PFS container) are
**not accepted at the moment**. ShadowMountPlus can mount them, and they may be
accepted again later.

- A listing made before this rule that is an image stays listed as it is, and
  its record keeps working. Its next release in the catalog must be a `.zip`.
- You can still attach image files to your GitHub release for people who
  prefer them. The catalog links the `.zip`.
- The store API reports each app's `format`. A client that installs only
  `zip` should show other formats as not installable rather than hide them.

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
- Raise `contentVersion` in `sce_sys/param.json` with every release and keep
  that file in your repository; it is how consoles find updates
  ([App versions](versioning.md)).
- Use the same title ID as `titleId` in `sce_sys/param.json`, and keep the
  title ID, `conceptId` and `contentId` stable across releases so updates keep
  the app's data.
- Keep user data out of the app itself, in writable locations such as
  `/download0`, which survive replacing the app.
- Never replace an asset that is already listed; publish a new release instead.
