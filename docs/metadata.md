# Metadata format

Each app is one UTF-8 JSON file at `apps/<TITLEID>.json`, at most 8 KiB,
containing a single object with **exactly** the eleven string fields below. No
field may be empty or missing, and no other fields are allowed.

| Field | Max length | Rules |
| --- | ---: | --- |
| `titleid` | 9 | Four uppercase letters and five digits, e.g. `PPSA01234`. Must equal the filename, and should equal the app's `titleId` in `sce_sys/param.json`. `PPSA99999` is reserved. |
| `name` | 64 | Display name. Unique across the catalog, ignoring case. |
| `kind` | 4 | `app`, `game` or `tool`. |
| `description` | 200 | One short plain-text sentence. No Markdown or HTML; it is displayed as text. |
| `license` | 64 | SPDX identifier or expression (`GPL-3.0`, `MIT OR Apache-2.0`). Must agree with the license GitHub detects for `source_repo`. |
| `author` | 64 | Developer or publisher name, as you want it credited. |
| `version` | 32 | Version shown to users. Letters, digits and `. + _ -`, e.g. `01.000.005` or `0.2.0-alpha.1`. |
| `source_repo` | 200 | `https://github.com/<owner>/<repository>`, using GitHub's exact capitalization. Must be public. |
| `artifact_url` | 500 | `<source_repo>/releases/download/<tag>/<asset>` for a published release; the asset ends in `.zip`, `.ffpfsc` or `.ffpkg`. Moving links such as `/releases/latest/download/` are rejected. Unique across the catalog. |
| `sha256` | 64 | SHA-256 of the artifact as 64 lowercase hex characters. Unique across the catalog. |
| `icon_url` | 500 | Direct HTTPS link ending in `.png`, `.jpg`, `.jpeg` or `.webp`, returning that image type, at most 2 MiB. Square, 256×256 or larger recommended. Pin to a tag or commit. |

## Text rules

All values must be NFC-normalized Unicode without leading or trailing
whitespace. Control characters, line breaks, invisible formatting characters
(including bidirectional overrides and zero-width characters), private-use and
unassigned code points are rejected. This keeps names from being visually
spoofed and keeps records safe to render anywhere.

## JSON rules

- Duplicate keys are rejected, even with identical values.
- Values must be strings; numbers and `null` are rejected.
- Formatting is free, but the repository uses two-space indentation and field
  order as shown in the [README](../README.md#record-format).

## Why these fields

The record carries only what the website and the console store need to show an
app and to install one exact, verified release. Release history, sizes and
compatibility notes stay in the developer's repository. The sha256 is what ties
a reviewed listing to the bytes users download.
