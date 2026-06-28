---
name: Slow homepage root cause & fix
description: Why bazar.uk homepage becomes slow (5s+) after edits, and the exact fix pattern
---

## The root cause pattern

`bazar.uk` homepage calls `/api/properties/recent-enriched` (Python server.py).
This endpoint used to launch **N parallel HTTP threads** (one per listing, up to 12) each calling `admin.bazar.uk/api/properties/{id}` (Laravel `show()`), waiting up to `t.join(timeout=5)`.

**Any change that makes `show()` slower** (extra DB query, slow JOIN, etc.) immediately makes the homepage slow, because 12 threads × slower show() = homepage hangs up to 5 seconds.

This happened repeatedly:
- Adding a `Customer` lookup inside `show()` for `seller_registered` field → added 12 extra DB queries in parallel → 5s page load.
- Previous sessions had the same symptom for unknown reasons (user had to restore from backup).

## The fix (applied 28 Jun 2026)

Replaced the 12-thread HTTP approach with **2 batch MySQL queries** directly in server.py `recent-enriched` handler:

```python
# ONE connection, TWO queries:
# 1. SELECT id, old_price, district, listing_type, images, car_make, phone_brand,
#    job_type, employment_type, workplace_type, salary_period, description,
#    created_at, firebase_uid FROM properties WHERE id IN (...)
# 2. SELECT property_id, COUNT(*) AS cnt FROM property_views
#    WHERE property_id IN (...) GROUP BY property_id
```

Then merge results into `enriched_list` in Python — no HTTP roundtrips to admin.bazar.uk.

**Location in server.py:** Search for `STEP 2: batch-fetch extra fields from MySQL in ONE query`

## Critical serialization gotchas

MySQL via pymysql returns:
- `DECIMAL` columns (e.g. `old_price`, `price`) → Python `Decimal` → **not JSON serializable** → crashes with `TypeError: Object of type Decimal is not JSON serializable`
- `DATETIME` columns (e.g. `created_at`) → Python `datetime` → **not JSON serializable**

**Fix:**
```python
_op = row.get('old_price')
enriched_list[idx]['old_price'] = float(_op) if _op is not None else None

_cat = row['created_at']
enriched_list[idx]['created_at'] = _cat.strftime('%Y-%m-%d %H:%M:%S') if hasattr(_cat, 'strftime') else str(_cat)
```

## Diagnosis checklist when homepage is slow

1. Check journalctl: `journalctl -u bazar-seo -n 50 --no-pager`
2. Look for `TypeError`, timeouts, or repeated HTTP errors
3. Test endpoint directly: `curl -s 'http://localhost:5000/api/properties/recent-enriched' | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))`
4. If show() was recently changed → check if it added extra DB queries → move those queries OUT of show() or batch them in recent-enriched instead
5. **Rule:** Never add slow operations to `show()` without considering that `recent-enriched` calls it 12 times

## Where things live

- Python handler: `server.py` → search `recent-enriched`
- Laravel show(): `/var/www/bazar-dev/app/Http/Controllers/PropertyApiController.php` → `public function show($id)`
- Production service: `systemctl restart bazar-seo`
- Deploy: `scp -i .local/ssh/bazar_deploy server.py root@49.13.231.137:/var/www/bazar-prod/server.py`
