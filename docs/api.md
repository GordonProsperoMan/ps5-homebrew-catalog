# Store API

The catalog publishes itself as static JSON under
`https://homebrew.page/api/v1/`, for a console store, for apps that check
whether they have an update, and for any other client. This page is the
specification: the files, every field, how to find updates, and what stays
stable.

The API is generated from the records in [`apps/`](../apps) on every merge to
`main`. The records are the single source of truth; nothing is edited in the
API itself, and there is no server behind it, only files on a CDN.

## Files

| Path | Holds | Size | Use it to |
| --- | --- | --- | --- |
| [`/api/v1/versions.json`](https://homebrew.page/api/v1/versions.json) | The current version of every available app | about 65 bytes per app | check many installed apps for updates in one request |
| [`/api/v1/index.json`](https://homebrew.page/api/v1/index.json) | One compact entry per app, reservations included | about 330 bytes per app | show the catalog as a list |
| `/api/v1/apps/<TITLEID>.json` | Everything about one app | about 1 KB | show one app, install it, or let an app check itself |
| `/api/v1/icons/<TITLEID>.png` | The app's icon as PNG, at most 512 px on its longer side | varies | show the icon without a WebP decoder |
| `/api/v1/icons/<TITLEID>-256.png` | The same, at most 256 px | varies | lists and grids |

Sizes are uncompressed and for planning only. All JSON is UTF-8 and minified.
An unknown title ID answers with HTTP 404 (and an HTML body, which clients
ignore).

The older [`/catalog/v1.json`](website.md#older-feed-catalogv1json) feed is
still published and unchanged; new clients should use the API.

## One app: `apps/<TITLEID>.json`

```json
{
  "schema": 2,
  "titleid": "PPSA99039",
  "name": "EVO Player",
  "kind": "app",
  "description": "Media player for PS5 that plays video from USB or internal storage, …",
  "license": "GPL-3.0",
  "author": "Sain Saji",
  "version": "0.10.0",
  "source_repo": "https://github.com/sainsaji/EVO-PLAYER-PS5",
  "artifact_url": "https://github.com/sainsaji/EVO-PLAYER-PS5/releases/download/v0.10.0/EVOPlayer-v0.10.0-PPSA99039.ffpfsc",
  "sha256": "a2b14616a2662a5e8401aad9012ba1c0d3df68211e5b70039eedfb9a0845a0be",
  "icon_url": "https://raw.githubusercontent.com/sainsaji/EVO-PLAYER-PS5/v0.10.0/projects/evoplayer/sce_sys/icon0.png",
  "status": "available",
  "content_version": "01.000.001",
  "format": "ffpfsc",
  "artifact_name": "EVOPlayer-v0.10.0-PPSA99039.ffpfsc",
  "size": 21561344,
  "tag": "v0.10.0",
  "released": "2026-09-22T18:23:50Z",
  "prerelease": false,
  "release_url": "https://github.com/sainsaji/EVO-PLAYER-PS5/releases/tag/v0.10.0",
  "updated": "2026-09-29T17:20:37Z",
  "page": "https://homebrew.page/app/PPSA99039/",
  "icon": "https://homebrew.page/api/v1/icons/PPSA99039.png",
  "icon_small": "https://homebrew.page/api/v1/icons/PPSA99039-256.png",
  "icon_hash": "5b0c1e7a9d3f4a26"
}
```

The first eleven fields after `schema` are the app's record, exactly as in
[Metadata format](metadata.md). The build adds the rest:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema` | integer | Schema revision of this file; see [Versioning of the API](#versioning-of-the-api). |
| `status` | string | `available`: the app has a release and can be installed. `coming_soon`: the title ID is [reserved](submitting.md#reserving-a-title-id) and nothing can be downloaded yet. |
| `content_version` | string or null | The release's `contentVersion` from its `sce_sys/param.json`, in the PlayStation format `NN.NNN.NNN` (`01.000.070`). **This is the value to compare with an installed copy**; see [Finding updates](#finding-updates). `null` when it isn't known. |
| `format` | string or null | `zip`, `ffpkg` or `ffpfsc`; see [Artifact formats](artifact-formats.md) for how each is installed. |
| `artifact_name` | string or null | File name of the download. |
| `size` | integer or null | Size of the download in bytes. |
| `tag` | string or null | The GitHub release tag. `version` is this tag, or this tag without a leading `v`. |
| `released` | string or null | When the developer published the release. |
| `prerelease` | boolean or null | Whether the developer marked the release as a pre-release. The catalog lists an app's newest release, pre-releases included. |
| `release_url` | string or null | The release's page on GitHub, with the developer's notes. |
| `updated` | string or null | When the app's record last changed in the catalog. |
| `page` | string | The app's page on the website. |
| `icon` | string or null | PNG icon, at most 512 px on its longer side. |
| `icon_small` | string or null | PNG icon, at most 256 px. Falls back to `icon` when only one size exists. |
| `icon_hash` | string or null | Fingerprint of the app's icon: 16 hexadecimal characters that change when, and only when, the developer's image changes. `null` when there is no icon. See [Caching icons](#caching-icons). |

Rules that hold for every file:

- **Times** are ISO 8601 in UTC with a `Z`: `2026-09-22T18:23:50Z`.
- **`null` means unknown or not applicable**, never an empty string. In a
  reservation every release field is `null`. In an available app, `size`,
  `released`, `prerelease` and `content_version` can still be `null` for a
  while after a new release is listed, when GitHub couldn't be asked during
  that build; the next build fills them in. Clients must cope with both.
- **`artifact_url` and `sha256` are never `null` for an available app.** They
  are the reviewed part of the listing.
- **Icons are optional.** Use your own placeholder when `icon` is `null`.

### Installing from this file

1. Download `artifact_url`. It redirects to GitHub's file host; follow
   redirects.
2. Compute the SHA-256 of what you downloaded and compare it with `sha256`.
   **Install nothing that doesn't match.** The developer replacing a release
   file changes its hash; the catalog's daily health check then flags the
   listing.
3. Install according to `format` ([Artifact formats](artifact-formats.md)).

`size` lets a client show progress and check free space first; when it is
`null`, use the download's `Content-Length`.

## The list: `index.json`

```json
{
  "schema": 2,
  "generated": "2026-10-02T18:26:14Z",
  "commit": "bbb7e4475b867c486a05d1639023df3f03edc28e",
  "count": 18,
  "apps": [
    {
      "titleid": "PPSA99002",
      "status": "available",
      "name": "ProsperoLight",
      "kind": "app",
      "author": "BlackBearReloaded",
      "version": "01.000.070",
      "content_version": "01.000.070",
      "format": "zip",
      "size": 36383357,
      "released": "2026-10-01T01:50:46Z",
      "updated": "2026-10-01T04:17:55Z",
      "icon_small": "https://homebrew.page/api/v1/icons/PPSA99002-256.png",
      "icon_hash": "9f2c4d7e1a6b3c58"
    }
  ]
}
```

`apps` is sorted by title ID and includes reservations (`status` tells them
apart). Each entry is a subset of the app's own file, with the same meanings;
fetch `apps/<TITLEID>.json` for the description, license, download and hash.
`icon_hash` is there so a list can keep its icons; see [Caching icons](#caching-icons).
`generated` and `commit` say which build of the catalog this is; `count` is the
length of `apps`.

## Versions: `versions.json`

```json
{
  "schema": 2,
  "apps": {
    "PPSA99002": { "content_version": "01.000.070", "version": "01.000.070" },
    "PPSA99039": { "content_version": "01.000.001", "version": "0.10.0" },
    "PPSA99420": { "content_version": null, "version": "0.9" }
  }
}
```

Every available app, keyed by title ID; reservations aren't in it. It changes
only when an app's version does.

## Finding updates

The console reports a `contentVersion` for every installed title, read from the
title's `sce_sys/param.json`. The catalog publishes the same value for the
listed release as `content_version`, so no client has to guess what a release
tag means.

**Format.** `NN.NNN.NNN`: two digits, three digits, three digits
(`01.000.070`). Compare two versions as three integers, left to right;
comparing the strings character by character gives the same order.

**The rule.** An update is available when the catalog's `content_version` is
**higher** than the installed `contentVersion`.

| Catalog `content_version` | Installed `contentVersion` | Result |
| --- | --- | --- |
| `01.000.070` | `01.000.060` | Update available |
| `01.000.070` | `01.000.070` | Up to date |
| `01.000.070` | `01.000.080` | Up to date: the installed copy is newer than the listing (a development build, or a release the catalog hasn't picked up yet) |
| `null` | anything | Unknown: say so, or say nothing. Don't offer an update. |
| anything | not in the format | Unknown |

`version` is for display. It is the developer's release tag (`0.10.0`,
`vk-285-117`), has no defined order, and must not be used to decide whether an
update exists.

When `content_version` is `null`, the developer hasn't given the catalog a way
to read it; [App versions](versioning.md) explains what they need to do.
Clients can still show the app and install it.

### An app checking itself

1. `GET https://homebrew.page/api/v1/apps/<your title ID>.json`.
2. If the answer isn't HTTP 200, `status` isn't `available`, or
   `content_version` is `null`, stop: there is nothing to report.
3. Compare `content_version` with the `contentVersion` of your own
   `param.json` using the rule above.
4. If there is an update, tell the user and point them at `page` or
   `release_url`. Show `version` as the name of the new release.

Do this in the background, at most once per launch, and never make the app
wait for it or fail because of it: the catalog may be unreachable, and the
user may be offline.

### A store checking what is installed

1. `GET https://homebrew.page/api/v1/versions.json`: one request, however many
   apps are installed, and the catalog never learns which ones they are.
2. For each installed title ID that is in `apps`, apply the rule.
3. Fetch `apps/<TITLEID>.json` only for the apps the user opens or updates.

Installed titles that aren't in `versions.json` aren't listed in the catalog.

## Caching icons

Icons are the largest files in the API, and they rarely change. A client
should download each one once and keep it:

1. Store every icon you download together with the `icon_hash` it came with.
2. When you read `index.json` (or an app's own file), compare each app's
   `icon_hash` with the one you stored.
3. Download the icon again only when they differ, or when you have none. When
   `icon_hash` is `null`, the app has no icon: show your placeholder.

An unchanged icon then costs no request at all. `icon_hash` covers both sizes,
and it is independent of the app's version: a new release with the same image
keeps it, and an image the developer replaces changes it. Treat it as an
opaque string; only equality matters.

A client that keeps no fingerprints can still send `If-None-Match` for each
icon, as for any other file, at the cost of one request per icon.

## Requests

- **HTTPS only**, `GET` only. No key, no account, no rate limit to negotiate;
  be considerate anyway.
- **Caching.** Responses carry an `ETag` and
  `Cache-Control: public, max-age=300, must-revalidate`. Keep the `ETag` with
  your copy and send it back as `If-None-Match`; an unchanged file answers
  `304 Not Modified` with no body. A per-app file and `versions.json` keep
  their `ETag` across catalog builds until that app changes. `index.json`
  changes on every build.
- **Freshness.** A merged listing reaches the API within a few minutes, and
  caches may hold a file for five more. Checking more often than every few
  hours gains nothing.
- **Compression.** Send `Accept-Encoding: gzip` if your HTTP client can
  decompress; the files are small enough to work without it.
- **Browsers.** `Access-Control-Allow-Origin: *` is set on everything under
  `/api/`.
- **Failure.** Treat timeouts, non-200 answers and JSON that doesn't parse as
  "no information", and try again later.

## Versioning of the API

- **The path is the contract.** Everything under `/api/v1/` keeps its paths,
  field names, types and meanings.
- **Additions don't break it.** New fields and new files can appear at any
  time. `schema` is raised when they do, so a client can tell whether a field
  it wants exists yet. Clients must ignore fields they don't know.
- **A breaking change gets a new path**, `/api/v2/`: removing or renaming a
  field, changing its type or meaning, or changing the update rule. `/api/v1/`
  keeps being published next to it for at least six months after `v2` is
  announced in this document and in the repository's releases, so shipped apps
  keep working.
- **Don't build on anything else.** The website's pages, the hashed files under
  `/assets/`, and the repository's layout can change without notice.

| `schema` | Date | Change |
| --- | --- | --- |
| 1 | 2026-10-02 | First version: `versions.json`, `index.json`, `apps/<TITLEID>.json`, PNG icons. |
| 2 | 2026-10-02 | Added `icon_hash` to app files and index entries, so clients can cache icons without requests. |

## Where the values come from

| Value | Source | Checked |
| --- | --- | --- |
| The eleven record fields | `apps/<TITLEID>.json`, reviewed and merged by a maintainer | On every pull request, push and in the daily health check |
| `sha256` | The record; it must equal the digest GitHub computes for the file | Same |
| `size`, `released`, `prerelease` | GitHub's API for the release | Read when the release is first built into the site, then cached for that file |
| `content_version` | `sce_sys/param.json` in the app's repository at the release tag | Same; see [App versions](versioning.md) |
| `updated` | The record's history in this repository | Every build |
| Icons | `icon_url`, converted to PNG | Every build, cached |

No artifact is downloaded to produce any of it.
