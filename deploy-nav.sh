#!/bin/bash
set -e

LARAVEL_ROOT="/var/www/bazar-dev/app"
ARCHIVE_URL="https://5598a117-b706-47f3-b730-7bfffbf33d8c-00-1eu86075dpd9f.pike.replit.dev/bazar-admin-nav.tar.gz"

echo "=== Step 1: Verify Filament 5.x classes ==="

echo -n "NavigationItem: "
grep -rl "class NavigationItem" $LARAVEL_ROOT/vendor/filament/ 2>/dev/null | head -1 || echo "NOT FOUND"

echo -n "modifyQueryUsing: "
grep -rl "function modifyQueryUsing" $LARAVEL_ROOT/vendor/filament/ 2>/dev/null | head -1 || echo "NOT FOUND"

echo ""
echo "=== Step 2: Check existing Pages ==="
ls -la $LARAVEL_ROOT/app/Filament/Resources/PropertyResource/Pages/ 2>/dev/null || echo "Pages dir not found"

echo ""
echo "=== Step 3: Download and deploy ==="
cd /tmp
rm -f bazar-admin-nav.tar.gz
wget -q "$ARCHIVE_URL" -O bazar-admin-nav.tar.gz
echo "Downloaded archive"

tar xzf bazar-admin-nav.tar.gz -C $LARAVEL_ROOT/
echo "Extracted to $LARAVEL_ROOT"

echo ""
echo "=== Step 4: Clear caches ==="
cd $LARAVEL_ROOT
php artisan optimize:clear 2>/dev/null || php artisan cache:clear
php artisan filament:optimize-clear 2>/dev/null || true
php artisan view:clear
php artisan route:clear
echo "Caches cleared"

echo ""
echo "=== Step 5: Verify deployed files ==="
ls -la $LARAVEL_ROOT/app/Filament/Resources/PropertyResource.php
ls -la $LARAVEL_ROOT/app/Filament/Resources/PropertyResource/Pages/ListProperties.php

echo ""
echo "=== DONE! Test at https://dev.bazar.uk/admin ==="
