# Website

The store at <https://homebrew.page/ps5/> is a static site generated from
`apps/` by `python3 -m catalog build` and deployed by Cloudflare Pages on every
push to `main`. There is no server-side code, database or tracking.

## What the build produces

```text
dist/
├── _headers, _redirects        Cloudflare Pages security headers, caching, / → /ps5/
├── 404.html, robots.txt
└── ps5/
    ├── index.html              card view: every app as a holographic card
    ├── list/index.html         list view: compact rows with a quick download button
    ├── app/<TITLEID>/          one page per app: download, install steps, sha256
    ├── catalog/v1.json         feed for the console store and other clients
    └── assets/                 content-hashed CSS, JS and WebP icons
```

- **Two views, one set of filters.** Cards and List share a toolbar: search,
  type chips, status (available or coming soon), format and sort (name, title
  ID, type, recently updated). Filters live in the URL (`?q=…&kind=game&sort=updated`),
  and the Cards/List switch keeps them, so any filtered view can be linked.
- **Mobile-first layout.** On phones the cards form two columns, the list
  collapses to icon, name, a one-line summary and a download button, and the
  type chips scroll sideways.
- **Updated dates.** Each app shows when its record last changed on `main`,
  taken from the git history of `apps/<TITLEID>.json`. The build deepens a
  shallow clone first so dates stay correct on Cloudflare and CI.
- **Coming soon.** Title ID reservations appear as dimmed cards with a "Coming
  soon" badge and no download; see [Reserving a title ID](submitting.md#reserving-a-title-id).
- Every metadata value is HTML-escaped; descriptions render as plain text.
- Icons are fetched once per build from `icon_url`, resized to 512 px WebP (when
  Pillow is installed) and served from the site, so visitors never hit the
  original host. A broken icon becomes a placeholder with a build warning.
- Pages work without JavaScript; the script adds search, filters, sorting,
  copy buttons and card effects.
- The build fails, and Cloudflare keeps the previous deployment, if any record
  is invalid.

## Feed: `catalog/v1.json`

```json
{
  "schema": 1,
  "name": "PS5 Homebrew Catalog",
  "homepage": "https://homebrew.page/ps5/",
  "source": { "repository": "https://github.com/…/ps5-homebrew-catalog", "commit": "<sha>" },
  "apps": [
    { "…all eleven record fields…": "",
      "format": "zip | ffpkg | ffpfsc",
      "updated": "2026-09-28T22:30:46-04:00",
      "page": "https://homebrew.page/ps5/app/PPSA01234/",
      "icon": "https://homebrew.page/ps5/assets/icon-PPSA01234.<hash>.webp" }
  ],
  "coming_soon": [
    { "…all eleven fields, links and sha256 null…": "", "updated": "…", "page": "…", "icon": "…" }
  ]
}
```

`apps` holds only installable releases, so a client can install anything in it;
reservations are listed separately in `coming_soon`. Both are sorted by title
ID. `updated` is `null` when the history isn't available. The feed is served with
`Access-Control-Allow-Origin: *` and a five-minute cache. A breaking change
gets a new path (`v2.json`); `v1.json` keeps working.

## Design

The site uses the Holo theme: a collector's binder where every app is a
holographic trading card with foil, tilt and a numbered strip. Its templates and
stylesheet are in `site/themes/holo/`; `site/shared/` holds the script and
images. The generator can host further themes in `site/themes/` and select them
with `--theme`.

## Build and preview locally

```sh
pip install -r requirements.txt            # optional: WebP icons
python3 -m catalog build                   # writes dist/
python3 -m http.server --directory dist 8000
```

Open <http://localhost:8000/ps5/>. Useful options: `--no-icons` (offline,
placeholders), `--base /` (serve at the root), `--site-url` (origin used in the
feed and canonical links), `--out`.

## Cloudflare Pages setup

1. In Cloudflare, **Workers & Pages → Create → Pages → Connect to Git** and pick
   this repository.
2. Build settings:
   - Production branch: `main`
   - Framework preset: None
   - Build command: `python3 -m catalog build`
   - Build output directory: `dist`
   - Environment variable: `PYTHON_VERSION` = `3.13`
3. Cloudflare installs `requirements.txt` automatically before building.
4. **Custom domains → Set up a domain →** `homebrew.page`. With the domain's DNS
   on Cloudflare the certificate and records are created automatically. The
   site's `_redirects` sends `/` to `/ps5/`.
5. Optional: under **Settings → Builds → Branch control**, disable preview
   deployments for pull requests, so untrusted submissions never build on
   Cloudflare. The trusted submission check already validates every record.

Pages rebuilds on every push to `main`, including merged submissions, so a
merged pull request is live within a minute or two. A failed build leaves the
last good deployment online.
