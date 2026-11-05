#!/usr/bin/env bash
# deploy.sh — push dist/ to Hostinger public_html.
# Pick ONE method and fill in the variables (or set them in your environment).
set -euo pipefail
cd "$(dirname "$0")/.."

# ---- Method A: rsync over SSH (best; needs SSH on your Hostinger plan) ----
# SSH_USER=u123456789
# SSH_HOST=123.45.67.89          # or your domain
# SSH_PORT=65002                  # Hostinger commonly uses a non-22 port
# rsync -az --delete -e "ssh -p $SSH_PORT" dist/ "$SSH_USER@$SSH_HOST:public_html/"

# ---- Method B: FTP mirror with lftp (no SSH needed) ----
# lftp -c "set ftp:ssl-allow no; \
#   open -u $FTP_USER,$FTP_PASS $FTP_HOST; \
#   mirror -R --delete --parallel=4 dist/ /public_html/"

echo "deploy.sh: uncomment and configure one method above."
