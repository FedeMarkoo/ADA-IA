#!/usr/bin/env bash

set -euo pipefail

failures=0

report() {
  printf 'security policy violation: %s\n' "$1" >&2
  failures=$((failures + 1))
}

while IFS= read -r -d '' file; do
  case "$file" in
    .env|.env.*|*.pem|*.key|*.p12|*.pfx|*.jks|*.keystore|*.sqlite|*.sqlite3|*.db|*.db-shm|*.db-wal|*.sqlite-shm|*.sqlite-wal|application-local.yml|credentials/*|secrets/*)
      [ "$file" = ".env.example" ] || report "private file is tracked: $file"
      ;;
  esac
done < <(git ls-files -z)

if git grep -nI -E '(/home/[A-Za-z0-9._-]+|/Users/[A-Za-z0-9._-]+|[A-Za-z]:\\\\Users\\\\[A-Za-z0-9._-]+)' -- . ':(exclude)scripts/security/check-repository.sh'; then
  report "local absolute path found in tracked content"
fi

if git grep -nI -E '(BEGIN (RSA|EC|OPENSSH|DSA) PRIVATE KEY|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,})' -- . ':(exclude)scripts/security/check-repository.sh'; then
  report "credential or private key pattern found in tracked content"
fi

if [ "$failures" -gt 0 ]; then
  printf '%s security policy violation(s) found\n' "$failures" >&2
  exit 1
fi

printf 'repository security policy passed\n'
