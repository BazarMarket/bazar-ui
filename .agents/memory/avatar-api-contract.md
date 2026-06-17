---
name: Avatars vs job logos — two separate surfaces
description: Personal profile avatar (customer profile) is distinct from a job listing's company logo (per-listing image). Keep them separate.
---

# Avatars vs job logos

There are two visually-similar but distinct concepts. Do not merge them.

## 1. Personal profile avatar (per-customer)
- Stored on the customer profile; edited only in the cabinet.
- Returned by `GET /api/customers/{uid}` — which **never returns an empty `avatar`**: when none is set, server.py substitutes a default like `/icon/man.svg`.
- Shown on regular (non-job) product/grid cards (seller banner) via a `data-uid` img resolved by `_loadSellerAvatars`, and on the seller banner in `card.html`.
- **How to apply:** code deciding "real avatar vs initials" must treat any value containing `icon/` (leading slash optional) as "no real avatar" — filter with `value.indexOf('icon/') !== -1`.
- **Race condition:** `_loadSellerAvatars` caches per-uid; while a fetch is in flight the cache holds `'pending'`. Never apply the `'pending'` (or `'none'`) sentinel as an `img.src` — it blanks the image.

## 2. Job company logo (per-listing)
**Why:** a seller with many ads across sections must NOT get one shared avatar on every listing. The job logo belongs to the job listing, not the person.
- Uploaded in `post-ad.html` (jobs flow) and saved as a normal listing image via `images[]` — NOT PATCHed to the customer profile.
- Shown only in Jobs previews: `buildJobCard` in `search.html` uses `item.imgs[0]` (skipping the default `img/product.jpg` placeholder, else initials).
- **How to apply:** `card.html` already hides the gallery for `property_type` `job`/`job_seeking`, so the logo image does not leak onto the job detail page. If that gallery-hiding ever changes, re-check that the job logo isn't surfaced where it shouldn't be.
