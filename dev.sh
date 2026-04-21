#!/bin/bash
# ⛔ ЭТОТ СКРИПТ ЗАПУСКАЕТ ТОЛЬКО ПОЛЬЗОВАТЕЛЬ ВРУЧНУЮ.
# АГЕНТ НИКОГДА НЕ ЗАПУСКАЕТ ЭТОТ СКРИПТ САМОСТОЯТЕЛЬНО.
# Скрипт синхронизирует prod → dev на сервере.
# Агент не деплоит ничего на dev.bazar.uk ни при каких условиях.

if [ ! -f ~/.ssh/bazar_deploy ]; then
  mkdir -p ~/.ssh
  cp .local/ssh/bazar_deploy ~/.ssh/bazar_deploy
  chmod 600 ~/.ssh/bazar_deploy
fi
echo "=== Syncing Production → Dev ==="
ssh -i .local/ssh/bazar_deploy -o StrictHostKeyChecking=no root@49.13.231.137 "
  echo '--- Frontend files ---' &&
  rsync -av /var/www/bazar-prod/public/*.html /var/www/bazar-dev/public/ &&
  rsync -av /var/www/bazar-prod/public/css/   /var/www/bazar-dev/public/css/ &&
  rsync -av /var/www/bazar-prod/public/js/    /var/www/bazar-dev/public/js/ &&
  rsync -av /var/www/bazar-prod/public/img/   /var/www/bazar-dev/public/img/ &&
  rsync -av /var/www/bazar-prod/public/icon/  /var/www/bazar-dev/public/icon/ &&
  cp /var/www/bazar-prod/server.py /var/www/bazar-dev/server.py &&
  echo '--- Database: bazar_prod → bazar_dev ---' &&
  mysqldump -u bazar -pBazarSecure2026 bazar_prod 2>/dev/null | mysql -u bazar -pBazarSecure2026 bazar_dev 2>/dev/null &&
  echo 'DB sync done' &&
  systemctl restart bazar-seo-dev &&
  echo 'Dev server restarted'
"
echo "=== Done! Dev is now a full copy of Production ==="
