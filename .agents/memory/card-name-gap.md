---
name: card-name gap fix
description: Gap between seller name and "1 month with Bazar Market" in card.html seller block — root cause and fix.
---

## The rule
When adding content below the avatar (left column), the right column stretches to match height. `.card-name__text` has `margin-top: auto !important` which consumes the extra space and creates a visible gap.

**Why:** `.card-name__right` is `flex-direction: column` — `margin-top: auto` on a flex child pushes it to the bottom of available space.

**How to apply:**
- Add `align-items: flex-start` to `.card-name` so columns don't force each other's height
- Add `.card-name .card-name__text { margin-top: 0 !important; }` to cancel the auto margin in this specific block
- Add `.card-name__left .card-name__photo { margin-top: 0; }` to align avatar with top of right column

## Final layout (approved June 2026)
- Messenger icons (WA/TG/VB) positioned **below the avatar** in `card-name__left`, inside `.card-name__bottom > .network.card-name__network`
- Icon size: 22px, border-radius: 4px, margin-right: 3px between icons
- JS selectors use `.card-name__network .icon-wp/tg/vb` (not `.card-name__bottom .icon-*`)
- `.card-name` has `align-items: flex-start`
