#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
cd "$scratch"
git init -q
hook="$repo/examples/native-hook/.githooks/pre-commit"
test -x "$hook" || { printf 'Hook entry point absent: %s\n' "$hook" >&2; exit 1; }
export ANSIBLE_CI_CHECK="$repo/scripts/check.sh"
printf '# Unrelated Markdown\n' > README.md
git add -- README.md
ANSIBLE_CI_CHECK=/nonexistent/command "$hook"
cat >pass <<'YAML'
---
- name: Run synthetic fixture
  hosts: all
  gather_facts: false
  tasks:
    - name: Report fixture
      ansible.builtin.debug:
        msg: "synthetic"
YAML
sed 's/ansible.builtin.debug/debug/' pass >fail
cp fail play.yml
git add -- play.yml
cp pass play.yml
index=$(git write-tree)
worktree=$(sha256sum play.yml)
if "$hook"; then printf 'Staged lint violation passed.\n' >&2; exit 1; fi
test "$index" = "$(git write-tree)"
test "$worktree" = "$(sha256sum play.yml)"
git add -- play.yml
cp fail play.yml
index=$(git write-tree)
worktree=$(sha256sum play.yml)
"$hook"
test "$index" = "$(git write-tree)"
test "$worktree" = "$(sha256sum play.yml)"
