#!/bin/bash
echo "=== Deploying DEV → Production ==="
ssh -i ~/.ssh/bazar_deploy -o StrictHostKeyChecking=no root@49.13.231.137 "bash /root/bazar-deploy.sh"
echo "=== Done! ==="
