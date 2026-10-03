# Metadata format

Each app is one UTF-8 JSON file at `apps/<TITLEID>.json`, at most 8 KiB,
containing a single object with **exactly** the eleven fields below. No field
may be missing and no other fields are allowed. Values are non-empty strings;
only [reservations](#reservations-coming-soon) use `null`.

| Field | Max length | Rules |
| --- | ---: | --- |
| `titleid` | 9 | Four uppercase letters and five digits, e.g. `PPSA01234`. Must equal the filename, and should equal the app's `titleId` in `sce_sys/param.json`. `PPSA99999` is reserved. |
| `name` | 64 | Display name. Unique across the catalog, ignoring case. |
| `kind` | 4 | `app`, `game` or `tool`. |
| `description` | 200 | One short plain-text sentence. No Markdown or HTML; it is displayed as text. |
| `license` | 64 | SPDX identifier or expression (`GPL-3.0`, `MIT OR Apache-2.0`). Must agree with the license GitHub detects for `source_repo`. |
| `author` | 64 | Developer or publisher name, as you want it credited. |
| `version` | 32 | Version shown to users: the release tag in `artifact_url`, optionally without a leading `v` (tag `v0.2.0-alpha.1` → `0.2.0-alpha.1`). Letters, digits and `. + _ -`. Consoles find updates with the release's `contentVersion` instead, which the catalog reads from your repository; see [App versions](versioning.md). |
| `source_repo` | 200 | `https://github.com/<owner>/<repository>`, using GitHub's exact capitalization. Must be public. |
| `artifact_url` | 500 | `<source_repo>/releases/download/<tag>/<asset>` for a published release; the asset is a `.zip` of the app folder, the only [format](artifact-formats.md) accepted at the moment. Moving links such as `/releases/latest/download/` are rejected. Unique across the catalog. |
| `sha256` | 64 | SHA-256 of the artifact as 64 lowercase hex characters. Unique across the catalog. |
| `icon_url` | 500 | Direct HTTPS link ending in `.png`, `.jpg`, `.jpeg` or `.webp`, returning that image type, at most 2 MiB. Square; 512×512 recommended (the size of `sce_sys/icon0.png`), 256×256 at least. Larger images are scaled down to 512 px. Pin to a tag or commit. |

## Reservations (coming soon)

A title ID can be reserved before its first release. A reservation has the same
eleven fields, with the release-specific ones empty:

| Field | In a reservation |
| --- | --- |
| `artifact_url` | `null`. This is what marks the record as a reservation. |
| `source_repo`, `icon_url`, `sha256` | Must be `null`. |
| `version`, `license` | `null`, or a value following the rules above. |
| `titleid`, `name`, `kind`, `description`, `author` | Required, same rules as above. |

`null` is allowed nowhere else. A reservation belongs to the GitHub account
that added it, and each account can hold at most 5. See
[Reserving a title ID](submitting.md#reserving-a-title-id).

## Text rules

All values must be NFC-normalized Unicode without leading or trailing
whitespace. Control characters, line breaks, invisible formatting characters
(including bidirectional overrides and zero-width characters), private-use and
unassigned code points are rejected. This keeps names from being visually
spoofed and keeps records safe to render anywhere.

## JSON rules

- Duplicate keys are rejected, even with identical values.
- Values must be strings; numbers are rejected, and `null` is accepted only in
  reservations.
- Formatting is free, but the repository uses two-space indentation and field
  order as shown in the [README](../README.md#record-format).

## Why these fields

The record carries only what a person has to state and a maintainer has to
review: what the app is, and which exact file is listed. The sha256 is what
ties a reviewed listing to the bytes users download.

Everything a machine can read for itself stays out of the record. The download
size, the release date and the content version are added to the
[store API](api.md) by the build, from GitHub and from the app's repository, so
they can't disagree with the release. Release history and compatibility notes
stay in the developer's repository.
