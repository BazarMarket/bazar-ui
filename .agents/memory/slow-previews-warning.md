---
name: Slow previews after Jobs deploy
description: Homepage/search previews became very slow after Jobs section work; backup restore fixed it
---

## Rule
After deploying changes to search.html, post-ad.html or card.html — immediately check homepage preview loading speed. If slow: do NOT keep iterating, restore from backup.

**Why:** During Jobs UI session (27 June 2026), something in the deployed changes caused homepage listing previews to load very slowly. The user had to restore from backup twice. Exact cause was not isolated — possibly browser caching interaction, CSS affecting image rendering, or MutationObserver overhead. After clean redeploy of only the Jobs files (without touching index.html, script.js, server.py, or header-auth.js), speed returned to normal.

**How to apply:**
- Never touch index.html, script.js, header-auth.js, or server.py when working on Jobs UI
- After any deploy, ask user to confirm page speed before continuing
- Keep .local/jobs-backup/ up to date so restore is always possible in one command
