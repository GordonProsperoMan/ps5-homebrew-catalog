# PS5 Homebrew Catalog

Community-maintained metadata for PS5 homebrew. The initial records cover the eight titled apps and six additional projects listed on [BlackBearReloaded's project site](https://blackbearreloaded.github.io/).

Each app has one YAML file in [apps](apps/) and a small icon in [assets/icons](assets/icons/). App records link to exact GitHub Release ZIPs owned by their publishers. Research, runtime, and starter projects are listed without an installable artifact unless a specific app package exists.

The published ZIPs were downloaded, hashed, and inspected when these entries were created. Each app archive has one title ID directory containing `eboot.bin`, `sce_sys/param.json`, and `sce_sys/icon0.png`. `installed_bytes` is the sum of uncompressed file sizes in the ZIP. ProsperoEden's SHA-256 was calculated from its release ZIP because that release has no checksum sidecar.

`installation_verified: false` means the archive has **not** yet been tested with the planned store and launcher on PS5 hardware. The website may offer its direct download link, but a store must not present it as a verified one-click install. The implementation plan remains in the local PS5 workspace for now.

## Validate metadata

Install the single build-time dependency and run the local check:

```sh
python3 -m pip install -r requirements.txt
python3 scripts/validate.py
```

The same check runs on pull requests. It validates metadata structure, unique IDs and title IDs, icon files, and release link/size/hash fields without executing or downloading submitted artifacts.

See [CONTRIBUTING.md](CONTRIBUTING.md) to add or update a project. The website generator, Cloudflare deployment, and PS5 client are later milestones.
