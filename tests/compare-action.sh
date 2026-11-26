#!/usr/bin/env bash
set -euo pipefail
[[ $COMPOSITE_FAILURE == failure ]]
out=$(mktemp)
log=$(mktemp)
trap 'rm -f -- "$out" "$log"' EXIT
ANSIBLE_CI_WORKING_DIRECTORY=tests/fixtures/pass GITHUB_OUTPUT="$out" scripts/check.sh
grep -Fx "python-version=$ACTION_PYTHON_VERSION" "$out"
grep -Fx "ansible-core-version=$ACTION_CORE_VERSION" "$out"
grep -Fx "ansible-lint-version=$ACTION_LINT_VERSION" "$out"
if ANSIBLE_CI_WORKING_DIRECTORY=tests/fixtures/fail scripts/check.sh >"$log" 2>&1; then
  printf '%s\n' 'The failing fixture passed directly.' >&2
  exit 1
fi
grep -F 'jinja[spacing]' "$log"
