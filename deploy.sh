#!/bin/bash
# Deploy changed files from Replit directly to Production
# Usage: bash deploy.sh file1.html file2.html css/main.css ...
set -e

if [ ! -f .local/ssh/bazar_deploy ]; then
  echo "ERROR: SSH key not found at .local/ssh/bazar_deploy"
  exit 1
fi

PROD_ROOT="root@49.13.231.137:/var/www/bazar-prod/public"
SSH_KEY=".local/ssh/bazar_deploy"
SSH_OPTS="-o StrictHostKeyChecking=no -i $SSH_KEY"

if [ "$#" -eq 0 ]; then
  echo "Usage: bash deploy.sh file1.html css/main.css ..."
  exit 1
fi

for FILE in "$@"; do
  echo "--- Deploying: $FILE"
  scp $SSH_OPTS "$FILE" "$PROD_ROOT/$FILE"
done

echo "=== Production updated ==="

# Also push to GitHub so repo stays in sync
echo "--- Pushing to GitHub..."
git push https://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@github.com/BazarMarket/bazar-ui.git main 2>&1 | tail -3

echo "=== Done! ==="
