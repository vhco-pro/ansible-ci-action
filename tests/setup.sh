#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
version=$("$repo/scripts/setup.sh" pin)
expected=$(awk '$1 == "python" { print $2 }' "$repo/scripts/.tool-versions")
[[ $version == "$expected" ]]
printf 'invalid archive\n' > "$scratch/invalid.tar.gz"
if "$repo/scripts/setup.sh" install "$scratch/tools" "$scratch/invalid.tar.gz" >"$scratch/log" 2>&1; then
  printf 'A wrong checksum passed.\n' >&2
  exit 1
fi
grep -F 'checksum' "$scratch/log"
test ! -e "$scratch/tools/venv/bin/ansible-lint"
"$repo/scripts/setup.sh" install "$scratch/tools"
ANSIBLE_CI_PYTHON="$scratch/tools/venv/bin/python" "$repo/scripts/setup.sh" versions
cp -a "$repo/scripts" "$scratch/corrupt"
sed -i -E 's/--hash=sha256:[a-f0-9]{64}/--hash=sha256:0000000000000000000000000000000000000000000000000000000000000000/g' "$scratch/corrupt/requirements.txt"
if "$scratch/corrupt/setup.sh" install "$scratch/corrupt-tools" >"$scratch/log" 2>&1; then
  printf 'A wrong Python package hash passed.\n' >&2
  exit 1
fi
grep -i 'hash' "$scratch/log"
test ! -e "$scratch/corrupt-tools/venv/bin/ansible-lint"
