# Local Pre-Commit Hook Setup

This hook runs the sensitive data scanner on staged files before commit.

## Requirements

- `gitleaks` installed (see https://github.com/gitleaks/gitleaks#installation)

## Install (symlink)

```bash
cd /path/to/repo
mkdir -p .git/hooks
ln -s ../../.github/hooks/pre-commit-sensitive-check.sh .git/hooks/pre-commit
chmod +x .github/hooks/pre-commit-sensitive-check.sh
```

## Verify

```bash
.git/hooks/pre-commit
```

## Notes

- The hook runs `gitleaks` plus the custom sensitive data scan on staged files.
- To bypass temporarily, use `git commit --no-verify`.
