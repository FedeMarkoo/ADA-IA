#!/usr/bin/env bash

set -euo pipefail

test_root=$(mktemp -d)
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
trap 'rm -rf "${test_root}"' EXIT
git -C "${test_root}" init -q
git -C "${test_root}" config user.name tester
git -C "${test_root}" config user.email tester@example.com
touch "${test_root}/README"
git -C "${test_root}" add README
git -C "${test_root}" commit -qm 'feat: initial functionality'

assert_version() {
  local expected=$1
  local actual
  actual=$(cd "${test_root}" && "${repo_root}/scripts/release/calculate-version.sh")
  [[ "${actual}" == "${expected}" ]] || { echo "Expected ${expected}, got ${actual}" >&2; exit 1; }
}

assert_version 0.1.0
git -C "${test_root}" tag v0.1.0
git -C "${test_root}" commit --allow-empty -qm 'fix: repair release trigger'
assert_version 0.1.1
git -C "${test_root}" commit --allow-empty -qm 'feat: add release dispatch'
assert_version 0.2.0
git -C "${test_root}" commit --allow-empty -qm 'feat!: change release contract'
assert_version 1.0.0

echo 'calculate-version.sh: all tests passed'
