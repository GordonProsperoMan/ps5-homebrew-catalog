# Catalog signing keys

The public halves of the two Ed25519 keys that can sign the
[store API](../docs/api.md#verifying-the-catalog). Clients carry both and
accept a signature from either.

| File | Key ID | Role |
| --- | --- | --- |
| `catalog-signing-1.pub.pem` | `da351006acb6e3c3` | Signs every deploy. Its private half is the `CATALOG_SIGNING_KEY` deployment secret. |
| `catalog-signing-2.pub.pem` | `eef399ea3007720a` | Spare. Its private half is kept offline by the maintainer. |

Private keys are never committed. The keys have no expiry. Changing a file
here changes which catalogs clients will accept, so it needs the same care as
a release.
