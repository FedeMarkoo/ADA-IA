#!/usr/bin/env bash

set -euo pipefail

initial_version="${INITIAL_VERSION:-0.1.0}"
latest_tag=$(git tag --list 'v[0-9]*.[0-9]*.[0-9]*' --sort=-version:refname | head -n 1)

if [[ -z "${latest_tag}" ]]; then
  printf '%s\n' "${initial_version}"
  exit 0
fi

commit_range="${latest_tag}..HEAD"
subjects=$(git log "${commit_range}" --format='%s')
bodies=$(git log "${commit_range}" --format='%b')

if ! grep -Eq '^(feat|fix|perf|refactor|docs|build|chore|test|ci)(\([^)]*\))?!?:' <<< "${subjects}" \
  && ! grep -q 'BREAKING CHANGE' <<< "${bodies}"; then
  exit 0
fi

version="${latest_tag#v}"
IFS=. read -r major minor patch <<< "${version}"

if grep -Eq '^[a-z]+(\([^)]*\))?!:' <<< "${subjects}" \
  || grep -q 'BREAKING CHANGE' <<< "${bodies}"; then
  major=$((major + 1)); minor=0; patch=0
elif grep -Eq '^feat(\([^)]*\))?:' <<< "${subjects}"; then
  minor=$((minor + 1)); patch=0
else
  patch=$((patch + 1))
fi

printf '%s.%s.%s\n' "${major}" "${minor}" "${patch}"
