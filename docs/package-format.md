# Package format: `homebrew-zip-v1`

Every listed artifact is a ZIP that holds one app folder, ready to be placed
under `/data/homebrew/` on the console, where loaders such as
[ShadowMountPlus](https://github.com/drakmor/ShadowMountPlus) discover it.

```text
<TITLEID>.zip
└── <TITLEID>/                  the only top-level entry
    ├── eboot.bin               required
    ├── sce_sys/
    │   ├── param.json          required; "titleId" must equal <TITLEID>
    │   ├── icon0.png
    │   └── ...
    ├── sce_module/             optional
    └── assets/                 optional read-only resources
```

The asset's filename is up to you; `<TITLEID>.zip` is conventional.

## Rules

The catalog rejects an artifact when any of these fail:

| Rule | Limit or requirement |
| --- | --- |
| Valid ZIP | Readable central directory; every file decompresses and passes its CRC check. |
| Single top-level folder | Every entry is inside `<TITLEID>/`; nothing else at the root. |
| Required files | `<TITLEID>/eboot.bin` and `<TITLEID>/sce_sys/param.json`. |
| Title ID | `param.json` is a JSON object whose `titleId` equals the record's `titleid`. |
| Safe paths | No absolute paths, drive letters, backslashes, `.`/`..` or empty components. |
| Entry types | Regular files and directories only; no symbolic links or special files. |
| No duplicates | No two entries whose paths differ only by letter case. |
| No encryption | Encrypted entries are rejected. |
| Size | At most 1 GiB compressed and 4 GiB unpacked, measured while decompressing. |
| Entry count | At most 20,000 entries. |
| Path length | At most 1,024 bytes per path and 255 bytes per component. |

These are the same checks a console installer must apply before writing to
`/data/homebrew`, so a listed package installs the same way everywhere.

## What does not belong in a package

- Install scripts, post-install commands or paths outside the app folder.
- A `data/homebrew/` tree or other absolute destination; the installer chooses
  the destination from the title ID.
- User data. Apps should keep settings and saves in writable locations such as
  `/download0`, which survive replacing the app folder.

## Updating an installed app

Keep the same title ID, `conceptId` and `contentId` in `param.json` across
releases so the console treats the new package as an update of the same title
and keeps its data.
