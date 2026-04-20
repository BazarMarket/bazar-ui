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
echo "=== Saving Production → Dev ==="
ssh -i .local/ssh/bazar_deploy -o StrictHostKeyChecking=no root@49.13.231.137 "
  rsync -av /var/www/bazar-prod/public/*.html /var/www/bazar-dev/public/ &&
  rsync -av /var/www/bazar-prod/public/css/   /var/www/bazar-dev/public/css/ &&
  rsync -av /var/www/bazar-prod/public/js/    /var/www/bazar-dev/public/js/ &&
  rsync -av /var/www/bazar-prod/public/img/   /var/www/bazar-dev/public/img/ &&
  rsync -av /var/www/bazar-prod/public/icon/  /var/www/bazar-dev/public/icon/ &&
  cp /var/www/bazar-prod/server.py /var/www/bazar-dev/server.py &&
  systemctl restart bazar-seo-dev
"
echo "=== Done! Dev is now a copy of Production ==="
