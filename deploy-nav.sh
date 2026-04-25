#!/bin/bash
set -e

# CORRECT: Laravel root is /var/www/bazar-dev, NOT /var/www/bazar-dev/app
LARAVEL_ROOT="/var/www/bazar-dev"
ARCHIVE_URL="https://5598a117-b706-47f3-b730-7bfffbf33d8c-00-1eu86075dpd9f.pike.replit.dev/bazar-admin-nav.tar.gz"

echo "=== Step 1: Verify Filament 5.x classes ==="

echo -n "NavigationItem: "
grep -rl "class NavigationItem" $LARAVEL_ROOT/vendor/filament/ 2>/dev/null | head -1 || echo "NOT FOUND"

echo -n "modifyQueryUsing: "
grep -rl "function modifyQueryUsing" $LARAVEL_ROOT/vendor/filament/ 2>/dev/null | head -1 || echo "NOT FOUND"

echo ""
echo "=== Step 2: Download and deploy ==="
cd /tmp
rm -f bazar-admin-nav.tar.gz
wget -q "$ARCHIVE_URL" -O bazar-admin-nav.tar.gz
echo "Downloaded archive"

tar xzf bazar-admin-nav.tar.gz -C $LARAVEL_ROOT/
echo "Extracted to $LARAVEL_ROOT"

echo ""
echo "=== Step 3: Clear caches ==="
cd $LARAVEL_ROOT
php artisan optimize:clear 2>/dev/null || php artisan cache:clear
php artisan filament:optimize-clear 2>/dev/null || true
php artisan view:clear
php artisan route:clear
echo "Caches cleared"

echo ""
echo "=== Step 4: Verify all deployed files ==="
for f in PropertyResource.php PropertyResource/Pages/ListProperties.php PropertyResource/Pages/CreateProperty.php PropertyResource/Pages/EditProperty.php; do
    if [ -f "$LARAVEL_ROOT/app/Filament/Resources/$f" ]; then
        echo "OK: $f"
    else
        echo "MISSING: $f"
    fi
done

echo ""
echo "=== DONE! Test at https://dev.bazar.uk/dev-admin ==="
