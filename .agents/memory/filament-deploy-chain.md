---
name: Filament admin deploy chain
description: How changes to Filament JS/PHP files propagate to admin.bazar.uk
---

## Цепочка деплоя Filament-файлов

Когда агент меняет Filament-файлы (JS, PHP), изменения нужно класть сразу в ТРИ места:

1. `/var/www/bazar-dev/public/js/filament-real-estate.js` (источник для dev.sh)
2. `/var/www/bazar-prod/public/js/filament-real-estate.js` (чтобы пережить `bash dev.sh`)
3. `/var/www/bazar-dev-admin/public/js/filament-real-estate.js` (реально серверный файл, который видит admin.bazar.uk)

То же касается PHP-файлов (например, AdminPanelProvider.php):
1. `/var/www/bazar-dev/app/Providers/Filament/AdminPanelProvider.php`
2. `/var/www/bazar-dev-admin/app/Providers/Filament/AdminPanelProvider.php`

После PHP-изменений запускать: `cd /var/www/bazar-dev-admin && php artisan optimize:clear`

**Почему:** dev.sh копирует bazar-prod/public/js/ → bazar-dev/public/js/ (перезаписывая!),
а потом bazar-dev → bazar-dev-admin. Если файл не обновлён в prod — он затрётся.

**push.sh** — только GitHub push, НЕ деплой на сервер. Не путать с dev.sh.
