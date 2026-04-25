#!/bin/bash
# ЭТОТ СКРИПТ ЗАПУСКАЕТ ТОЛЬКО ПОЛЬЗОВАТЕЛЬ ВРУЧНУЮ.
# АГЕНТ НИКОГДА НЕ ЗАПУСКАЕТ ЭТОТ СКРИПТ САМОСТОЯТЕЛЬНО.
#
# НАПРАВЛЕНИЕ: ТОЛЬКО прод -> dev. Никогда наоборот.
#   - Фронт:   /var/www/bazar-prod/public/ -> /var/www/bazar-dev/public/
#   - Admin:   /var/www/bazar-dev/{app,config,routes,resources,database} -> /var/www/bazar-dev-admin/
#   - База:    bazar_dev (прод) -> bazar_prod (dev)
#   - Сервер:  перезапуск bazar-seo-dev

if [ ! -f ~/.ssh/bazar_deploy ]; then
  mkdir -p ~/.ssh
  cp .local/ssh/bazar_deploy ~/.ssh/bazar_deploy
  chmod 600 ~/.ssh/bazar_deploy
fi

echo "=== Syncing Production -> Dev ==="
ssh -i .local/ssh/bazar_deploy -o StrictHostKeyChecking=no root@49.13.231.137 "
  echo '--- Frontend public/: prod -> dev ---' &&
  rsync -av /var/www/bazar-prod/public/*.html /var/www/bazar-dev/public/ &&
  rsync -av /var/www/bazar-prod/public/css/   /var/www/bazar-dev/public/css/ &&
  rsync -av /var/www/bazar-prod/public/js/    /var/www/bazar-dev/public/js/ &&
  rsync -av /var/www/bazar-prod/public/img/   /var/www/bazar-dev/public/img/ &&
  rsync -av /var/www/bazar-prod/public/icon/  /var/www/bazar-dev/public/icon/ &&
  echo '--- Frontend ROOT (SimpleHTTP fallback): prod -> dev ---' &&
  rsync -av /var/www/bazar-prod/*.html        /var/www/bazar-dev/ &&
  rsync -av /var/www/bazar-prod/js/           /var/www/bazar-dev/js/ &&
  cp /var/www/bazar-prod/server.py /var/www/bazar-dev/server.py &&
  echo '--- Admin isolation: bazar-dev -> bazar-dev-admin ---' &&
  rsync -a --delete /var/www/bazar-dev/app/       /var/www/bazar-dev-admin/app/ &&
  rsync -a --delete /var/www/bazar-dev/config/    /var/www/bazar-dev-admin/config/ &&
  rsync -a --delete /var/www/bazar-dev/routes/    /var/www/bazar-dev-admin/routes/ &&
  rsync -a --delete /var/www/bazar-dev/resources/ /var/www/bazar-dev-admin/resources/ &&
  rsync -a --delete /var/www/bazar-dev/database/  /var/www/bazar-dev-admin/database/ &&
  chown -R www-data:www-data /var/www/bazar-dev-admin/ &&
  echo 'Admin isolation synced' &&
  echo '--- Database: bazar_dev (прод) -> bazar_prod (dev) ---' &&
  mysqldump -u bazar -pBazarSecure2026 bazar_dev 2>/dev/null | mysql -u bazar -pBazarSecure2026 bazar_prod 2>/dev/null &&
  echo 'DB synced' &&
  systemctl restart bazar-seo-dev &&
  echo 'Dev server restarted'
"
echo "=== Done! Dev is now a full copy of Production ==="
