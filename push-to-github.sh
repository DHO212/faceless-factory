#!/bin/bash
# cara pakai: ./push-to-github.sh
# butuh: gh auth login dulu

set -e
REPO_NAME=${1:-faceless-factory}
echo "Creating repo $REPO_NAME ..."

# auth check
if ! gh auth status 2>&1 | grep -q "Logged in"; then
  echo "Belum login Github CLI. Jalankan:"
  echo "  gh auth login"
  echo "pilih Github.com -> HTTPS -> Yes -> Login with browser (copy code)"
  exit 1
fi

git add .devcontainer devcontainer.json requirements.txt main.py .env.example README-CODESPACE.md topics.txt .gitignore 2>/dev/null || git add .
git commit -m "faceless factory v1" 2>/dev/null || true
gh repo create "$REPO_NAME" --public --source=. --remote=origin --push 2>&1 | tee /tmp/gh_create.log
echo ""
echo "Done! Buka https://github.com/$(gh api user --jq .login)/$REPO_NAME"
echo "Lalu: Code -> Codespaces -> Create codespace on main"
