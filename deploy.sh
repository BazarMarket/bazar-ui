#!/bin/bash
# Deploy changed files from Replit directly to Production
# Usage: bash deploy.sh file1.html file2.html css/main.css ...
set -e

if [ ! -f .local/ssh/bazar_deploy ]; then
  echo "ERROR: SSH key not found at .local/ssh/bazar_deploy"
  exit 1
fi

SERVER="root@49.13.231.137"
PROD_ROOT="$SERVER:/var/www/bazar-prod/public"
SITE_ROOT="$SERVER:/var/www/bazar-prod"
SSH_KEY=".local/ssh/bazar_deploy"
SSH_OPTS="-o StrictHostKeyChecking=no -i $SSH_KEY"

if [ "$#" -eq 0 ]; then
  echo "Usage: bash deploy.sh file1.html css/main.css ..."
  exit 1
fi

for FILE in "$@"; do
  echo "--- Deploying: $FILE"
  BASENAME=$(basename "$FILE")

  # server.py lives at SITE_ROOT (not inside public/)
  if [[ "$FILE" == "server.py" ]]; then
    scp $SSH_OPTS "$FILE" "$SITE_ROOT/server.py"
    ssh $SSH_OPTS "$SERVER" "systemctl restart bazar-seo"
    echo "    Deployed server.py to SITE_ROOT and restarted bazar-seo"
    continue
  fi

  scp $SSH_OPTS "$FILE" "$PROD_ROOT/$FILE"

  # HTML-файлы Python-сервер читает из SITE_ROOT (не из public/)
  # Поэтому копируем их туда тоже
  if [[ "$FILE" == *.html ]]; then
    ssh $SSH_OPTS "$SERVER" "cp /var/www/bazar-prod/public/$FILE /var/www/bazar-prod/$BASENAME"
    echo "    Also synced to SITE_ROOT: $BASENAME"
  fi
done

echo "=== Production updated ==="
echo "=== Done! ==="
