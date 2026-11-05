#!/usr/bin/env bash
# deploy_dist.sh — publish dist/ to an orphan `deploy` branch, which Hostinger
# auto-deploys (same pattern as onlinebankreview / mutualfundreviewer). No FTP
# secrets; uses the Action's GITHUB_TOKEN. Hostinger: connect the repo once and
# point stocksreviewer.com at the `deploy` branch.
# This site is large (~5,700 files / ~230MB), so the push is tuned with a big
# http buffer and retried to ride out transient GitHub 500s.
set -euo pipefail
cd "$(dirname "$0")/.."
test -d dist || { echo "no dist/ to deploy"; exit 1; }

git config user.name  "stocksreviewer-bot"
git config user.email "noreply@anthropic.com"
git config http.postBuffer 1048576000   # 1GB, for the large pack
git config http.version HTTP/1.1         # HTTP/2 is flakier for big pushes

tmp="$(mktemp -d)"
cp -r dist/. "$tmp/"
# audit/build regenerate tracked files; discard them so the orphan switch is clean
git checkout -- . 2>/dev/null || true
git stash push --include-untracked --quiet -- data/ 2>/dev/null || true
git switch --orphan deploy 2>/dev/null || { git branch -D deploy 2>/dev/null || true; git switch --orphan deploy; }
git rm -rf . >/dev/null 2>&1 || true
cp -r "$tmp/." .
rm -rf "$tmp"
touch .nojekyll
git add -A
git commit -q -m "deploy $(date -u +%F' '%T) UTC" --allow-empty

ok=0
for attempt in 1 2 3 4 5; do
  echo "deploy push attempt $attempt…"
  if git push -f origin deploy; then ok=1; break; fi
  echo "push failed; retrying in $((attempt*15))s"
  sleep $((attempt*15))
done
git switch main
[ "$ok" = "1" ] || { echo "deploy push failed after retries"; exit 1; }
echo "deployed dist/ to the deploy branch"
