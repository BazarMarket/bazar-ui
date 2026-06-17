---
name: Avatar API contract (/api/customers/{uid})
description: The customers endpoint never returns an empty avatar — it substitutes a default icon path, so the frontend must filter it out to detect a real avatar.
---

# Avatar API contract

`GET /api/customers/{uid}` (served by server.py, proxying Laravel) **never returns an empty `avatar`**. When no real avatar is stored, server.py substitutes a default path like `/icon/man.svg` or `/icon/woman.png` based on gender.

**Why:** Other UI surfaces (header, chat) want a guaranteed image src. But list/card surfaces that fall back to initials (job cards, seller banner) must distinguish "real avatar" from "default placeholder."

**How to apply:** Frontend code deciding whether to show an avatar vs. initials must treat any value containing `icon/` (note: may or may not have a leading slash) as "no real avatar." Filter with `value.indexOf('icon/') !== -1`. This applies in `search.html` (`_loadSellerAvatars`) and `card.html` (seller banner).

**Related race condition:** `_loadSellerAvatars` in search.html uses an `_avatarCache` keyed by uid. While a fetch is in flight the cache holds `'pending'`. A second render must NOT apply the `'pending'` sentinel as an `img.src` (it would set src to the literal string "pending" and blank the image). Skip both `'none'` and `'pending'` when applying cached values.
