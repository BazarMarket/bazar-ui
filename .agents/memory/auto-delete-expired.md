---
name: Auto-delete expired listings
description: Background mechanism that auto-deletes expired property listings once per day
---

# Auto-delete expired listings

**Rule:** When asked "does auto-delete work?" or "what happens when days run out?" — the answer is YES, it exists and was set up months ago.

**Why:** Was configured in server.py + Laravel controller. Not a cron job — it's a Python background thread in server.py.

## How it works

1. `server.py` starts a daemon thread `_auto_delete_expired()` on startup
2. Waits 5 min after start, then runs every 24 hours
3. POSTs to `LARAVEL_API_BASE/properties/auto-delete-expired` with header `X-Bazar-Internal: moderation`
4. Laravel route: `POST /api/properties/auto-delete-expired` → `PropertyApiController::autoDeleteExpired()`

## Deletion logic (PropertyApiController.php ~line 607)

- If `expires_at` is set → deletes when `expires_at < now()`
- If `expires_at` is null → deletes when `created_at` (or `boosted_at`) + 30 days < now()
- Uses hard delete (`->delete()`) — records are permanently removed from DB
- Only callable from localhost / server IP with correct internal header

## Key files

- `/var/www/bazar-prod/server.py` — `_auto_delete_expired()` function (~line 5042)
- `/var/www/bazar-dev/app/Http/Controllers/PropertyApiController.php` — `autoDeleteExpired()` method (~line 607)
- `/var/www/bazar-dev/routes/api.php` — route registration (~line 55)
