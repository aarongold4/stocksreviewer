#!/usr/bin/env bash
# deploy_dist.sh — publish ONLY the contents of dist/ to the `deploy` branch as a
# single, fresh, force-pushed commit. Hostinger watches that branch.
#
# The commit is built in a THROWAWAY repo, so the live working tree is never
# switched, stashed, or cleaned. That guarantees the published branch is exactly
# dist/ and nothing else — no source, no __pycache__, no caches, no self-nested
# dist/. (The previous version switched the live repo to an orphan branch and ran
# `git add -A`; deleting the tracked .gitignore in that switch let git sweep the
# gitignored leftovers — dist/, pipeline/__pycache__, data/ — onto the branch,
# doubling its size. This approach removes that whole class of bug.)
set -euo pipefail
cd "$(dirname "$0")/.."
test -d dist || { echo "no dist/ to deploy"; exit 1; }

origin_url="$(git remote get-url origin)"
# Reuse whatever auth is already configured for this remote. On GitHub Actions,
# actions/checkout stores a token in an http extraheader — copy it so the
# throwaway repo can push. Locally this is usually empty and the push falls back
# to the user's SSH key / credential helper.
auth_key="$(git config --name-only --get-regexp '^http\..*\.extraheader$' 2>/dev/null | head -n1 || true)"
auth_val=""
[ -n "$auth_key" ] && auth_val="$(git config --get "$auth_key" 2>/dev/null || true)"

tmp="$(mktemp -d)"
cp -r dist/. "$tmp/"
touch "$tmp/.nojekyll"
(
  cd "$tmp"
  git init -q
  git checkout -q -b deploy
  git config user.name  "stocksreviewer-bot"
  git config user.email "noreply@anthropic.com"
  git config http.postBuffer 1048576000   # 1GB pack buffer for the large site
  git config http.version HTTP/1.1         # HTTP/2 is flakier for big pushes
  git add -A
  git commit -q -m "deploy $(date -u +%F' '%T) UTC" --allow-empty
)

push=(git -C "$tmp")
[ -n "$auth_val" ] && push+=(-c "$auth_key=$auth_val")
push+=(push -f "$origin_url" deploy:deploy)

ok=0
for attempt in 1 2 3 4 5; do
  echo "deploy push attempt $attempt…"
  if "${push[@]}"; then ok=1; break; fi
  echo "push failed; retrying in $((attempt*15))s"; sleep $((attempt*15))
done
rm -rf "$tmp"
[ "$ok" = "1" ] || { echo "deploy push failed after retries"; exit 1; }
echo "deployed $(find dist -type f | wc -l) files (dist/ contents only) to the deploy branch"
