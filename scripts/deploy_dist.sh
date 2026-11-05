#!/usr/bin/env bash
# deploy_dist.sh — publish dist/ to an orphan `deploy` branch, which Hostinger
# auto-deploys (same pattern as onlinebankreview / mutualfundreviewer). No FTP
# secrets needed; uses the Action's GITHUB_TOKEN. In Hostinger you connect the
# repo once and point stocksreviewer.com at the `deploy` branch.
set -euo pipefail
cd "$(dirname "$0")/.."
test -d dist || { echo "no dist/ to deploy"; exit 1; }

git config user.name  "stocksreviewer-bot"
git config user.email "noreply@anthropic.com"

# Build an orphan commit containing only dist/ contents at the repo root.
tmp="$(mktemp -d)"
cp -r dist/. "$tmp/"
git fetch origin deploy 2>/dev/null || true
git switch --orphan deploy 2>/dev/null || { git branch -D deploy 2>/dev/null || true; git switch --orphan deploy; }
git rm -rf . >/dev/null 2>&1 || true
cp -r "$tmp/." .
rm -rf "$tmp"
touch .nojekyll
git add -A
git commit -m "deploy $(date -u +%F' '%T) UTC" --allow-empty
git push -f origin deploy
git switch main
echo "deployed dist/ to the deploy branch"
