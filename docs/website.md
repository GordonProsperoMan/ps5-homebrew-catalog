# Website

The store at <https://homebrew.page/> is a static site generated from
`apps/` by `python3 -m catalog build` and deployed to Cloudflare Pages by GitHub
Actions on every push to `main`. There is no server-side code, database or tracking.

## What the build produces

```text
dist/
├── _headers, _redirects        Cloudflare Pages security headers, caching, redirects
├── 404.html, robots.txt
├── index.html                  the catalog: cards, or a compact list (?view=list)
├── tv/                         TV mode: the catalog as a 10-foot interface
├── app/<TITLEID>/              one page per app: download, install steps, sha256
├── catalog/v1.json             feed for the console store and other clients
└── assets/                     content-hashed CSS, JS and WebP icons
```

- **One catalog page, two views.** `/` holds both the cards and the list;
  the Cards/List switch changes view in place. Search, type chips, status
  (available or coming soon), format and sort apply to both and live in the URL
  (`?q=…&kind=game&sort=updated&dir=asc&view=list`), so any filtered view can be
  linked. The old `/list/` redirects there. The site used to live under
  `/ps5/`; every `/ps5/…` URL redirects to the same page at the root.
- **Sorting.** By name, updated date, developer, type or title ID, ascending or
  descending (the ↑/↓ button). In the list view, clicking a column header sorts
  by it, and clicking it again reverses the order. Updated dates default to newest
  first; everything else defaults to A to Z.
- **In-page navigation.** Opening an app fetches its static page and swaps its
  content in without reloading; Back returns to the catalog with the same
  filters, view, scroll position and focus. Every app page is still a complete
  HTML page, so direct links, link previews, search engines and browsers
  without JavaScript all work.
- **Mobile-first layout.** On phones the cards form two columns, the list
  collapses to icon, name, a one-line summary and a download button, and the
  type chips scroll sideways.
- **Updated dates.** Each app shows when its record last changed on `main`,
  taken from the git history of `apps/<TITLEID>.json`. The build deepens a
  shallow clone first so dates stay correct in CI.
- **Coming soon.** Title ID reservations appear as dimmed cards with a "Coming
  soon" badge and no download; see [Reserving a title ID](submitting.md#reserving-a-title-id).
- Every metadata value is HTML-escaped; descriptions render as plain text.
- Icons are fetched from `icon_url`, resized to 512 px WebP (when Pillow is
  installed) and served from the site, so visitors never hit the original host.
  The deploy job keeps them in a CI cache, so each icon URL is fetched only once
  across deploys. A broken icon becomes a placeholder with a build warning.
- Filtering waits for a pause in typing and only updates the view on screen;
  at 1,000 apps a filter change takes a few milliseconds.
- Pages work without JavaScript; the script adds search, filters, sorting,
  copy buttons and card effects.
- The build fails, and Cloudflare keeps the previous deployment, if any record
  is invalid.

## TV mode

`/tv/` is the catalog as a 10-foot interface for a television, driven by a
controller or a TV remote: a rail of sections (All, Apps, Games, Tools, Coming
soon), a grid of large tiles, and a full-screen page per app with the install
steps, the short link to open on a phone, and the SHA-256.

- **Controls.** The PS5 browser turns the controller into keys: the D-pad
  moves, ✕ (Enter) opens, ○ (Escape) goes back, △ (F1) changes the sort and □
  (F2) jumps to the rail. On an app's page, Left and Right step through the
  apps and Up and Down scroll. The TV remote's channel and track keys work too.
  Other browsers get the same controls from a connected gamepad (a DualSense
  over USB or Bluetooth, for example) through the Gamepad API, and the
  keyboard's arrows, Enter and Escape always work.
- **Automatic.** TV browsers are sent to TV mode before the regular page is
  drawn: the PS5 browser and common smart-TV browsers (Tizen, webOS, Android
  TV, Fire TV and others), recognised by their user agent. An app page opens
  the same app in TV mode, and catalog filters carry over.
- **Your choice sticks.** "Exit TV mode" returns to the regular layout and
  remembers it on that browser (`?layout=web`); the header's "TV mode" link
  (`?layout=tv`) goes back to the automatic choice. Both links work on any
  device.
- **Same data, no extra requests.** The build embeds the catalog in the page
  as JSON, and `tv.js` draws it with DOM APIs, so metadata is never parsed as
  HTML. The section, sort and open app live in the URL hash.

TV mode was inspired by [tv4play](https://github.com/ps5-payload-dev/tv4play)
by ps5-payload-dev, a 10-foot web app for the PS5 whose README documents how
the console's browser presents the controller.

## Feed: `catalog/v1.json`

```json
{
  "schema": 1,
  "name": "PS5 Homebrew Catalog",
  "homepage": "https://homebrew.page/",
  "source": { "repository": "https://github.com/…/ps5-homebrew-catalog", "commit": "<sha>" },
  "apps": [
    { "…all eleven record fields…": "",
      "format": "zip | ffpkg | ffpfsc",
      "updated": "2026-09-28T22:30:46-04:00",
      "page": "https://homebrew.page/app/PPSA01234/",
      "icon": "https://homebrew.page/assets/icon-PPSA01234.<hash>.webp" }
  ],
  "coming_soon": [
    { "…all eleven fields, links and sha256 null…": "", "updated": "…", "page": "…", "icon": "…" }
  ]
}
```

The feed is minified. `apps` holds only installable releases, so a client can install anything in it;
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

Open <http://localhost:8000/>. Useful options: `--no-icons` (offline,
placeholders), `--base /path/` (serve under a sub-path), `--site-url` (origin used in the
feed and canonical links), `--out`.

## Deployment

The **Deploy website to Cloudflare Pages** job in [CI](../.github/workflows/ci.yml)
builds `dist/` and uploads it with Cloudflare's Direct Upload (`wrangler pages
deploy`). It runs only on `main`, after the tests and the record verification
pass, so a broken or unverified catalog is never published. Cloudflare has no
access to this repository.

### What stays private

- **Nothing about the Cloudflare account is in the repository.** The API token
  and account ID are GitHub encrypted secrets. They aren't stored in files or
  history, they're masked in logs, and pull requests and forks can't read them.
- **The secrets reach only the deploy job.** They're environment secrets of
  `cloudflare-pages`, and that environment accepts only the `main` branch. The
  pull request workflows never use it.
- **Public logs stay clean.** Actions logs of a public repository are
  world-readable, so the deploy step keeps wrangler's output out of the log and
  prints only success, or on failure the error codes and messages with account
  IDs, emails, URLs and quoted values masked (`catalog/redact.py`). Wrangler
  telemetry is off.
- **The token can do one thing.** It can edit Cloudflare Pages in one account.
  It can't read DNS, billing or anything else, and you can revoke it at any time.
- **The site reveals nothing about the account.** Visitors see `homebrew.page`
  and the project's `*.pages.dev` name. Keep WHOIS privacy on for the domain;
  Cloudflare Registrar redacts owner details by default.

### One-time setup

1. **No project to create by hand.** The deploy job creates the Pages project
   (named after `CLOUDFLARE_PAGES_PROJECT`) on its first run. Don't use the
   dashboard's "Connect to Git", which installs Cloudflare's GitHub app and
   links the accounts.
2. **Create an API token.** Go to **My Profile → API Tokens → Create Token →
   Custom token**:
   - Permissions: **Account → Cloudflare Pages → Edit** (nothing else)
   - Account resources: **Include → your account**
   - TTL: optional; for example one year, with a reminder to rotate it
3. **Find the account ID.** It's shown in the Workers & Pages overview sidebar,
   and in the dashboard URL.
4. **Add them to GitHub**, not to the repository files. In the repository's
   **Settings → Environments → New environment**, create `cloudflare-pages`:
   - **Deployment branches and tags:** Selected branches → `main`
   - **Environment secrets:** `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`
5. **Switch deployment on.** Under **Settings → Secrets and variables → Actions
   → Variables**, add the repository variable `CLOUDFLARE_PAGES_PROJECT` =
   `homebrew-page`. The deploy job is skipped while this variable is missing.
6. **Deploy.** Go to **Actions → CI → Run workflow** on `main`, or push. Check
   `https://homebrew-page.pages.dev/`. If the name is taken on `pages.dev`,
   Cloudflare adds a suffix; the project's page in the dashboard shows the address.
7. **Connect the domain.** In the Pages project, go to **Custom domains → Set up
   a domain →** `homebrew.page`. An apex domain needs its DNS on Cloudflare; the
   certificate and records are then created automatically.

After that, every merge to `main` goes live within a couple of minutes. A failed
build or upload leaves the last good deployment online. To stop deployments,
delete the variable; to cut access entirely, revoke the token.
