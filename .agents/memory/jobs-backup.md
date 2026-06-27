---
name: Jobs section backup location
description: Where saved files live for post-backup restore of Jobs UI work
---

## Location
`.local/jobs-backup/` on Replit contains all Jobs-related changes from 27 June 2026 session.

## Files
- `search.html` — Jobs card UI, heart button (.jc-fav-btn), gap 29px, MutationObserver
- `post-ad.html` — Contact preference radio buttons + title limit 70 chars with overflow preview
- `card.html` — Hide phone/chat based on contact_preference
- `PropertyApiController.php` — contact_preference in validation, store, update, show
- `Property.php` — contact_preference in $fillable
- `RESTORE_INSTRUCTIONS.md` — exact deploy commands including DB ALTER TABLE

**Why:** User had to restore server backup twice during this session; this folder allows re-deploying just the Jobs changes cleanly without rewriting from scratch.
