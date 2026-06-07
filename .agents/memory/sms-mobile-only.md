---
name: SMS leads — mobile only
description: Only 07... UK mobile numbers are valid for SMS campaigns; landlines (01/02) must never be stored as phone leads or sent SMS.
---

Only mobile numbers starting with `07` are valid for SMS campaigns.

**Why:** 01... and 02... are UK landline numbers. Twilio and other SMS providers cannot send SMS to landlines. Sending to them wastes money and fails silently.

**How to apply:**
- In every scraper's `clean_phone()` function, add `.startswith('07')` check: `return d if UK_PHONE_RE.match(d) and d.startswith('07') and d not in FAKE_PHONES else None`
- In Filament SMS actions and Artisan commands, always filter `->where('phone', 'like', '07%')` before sending
- When cleaning up existing data: `UPDATE leads SET phone=NULL WHERE phone LIKE '01%' OR phone LIKE '02%'`
- The `leads` table UNIQUE key is on (phone, category) — NULLing landlines keeps the record (for place_id dedup) without blocking future inserts of the same landline from other businesses
