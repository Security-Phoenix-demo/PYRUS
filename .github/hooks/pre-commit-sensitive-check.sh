#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
mapfile -t staged_files < <(git diff --cached --name-only --diff-filter=ACMRT)

if [ "${#staged_files[@]}" -eq 0 ]; then
  exit 0
fi

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks is required for the pre-commit secret scan." >&2
  echo "Install: https://github.com/gitleaks/gitleaks#installation" >&2
  exit 1
fi

gitleaks detect --staged --redact --no-banner --source "$repo_root"

python "$repo_root/.github/scripts/scan_sensitive_data.py" --paths "${staged_files[@]}"
