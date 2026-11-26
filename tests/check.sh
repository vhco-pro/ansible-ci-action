#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
mkdir -p "$scratch/tree"
git -C "$scratch/tree" init -q
export ANSIBLE_CI_WORKSPACE="$scratch/tree"
check() { "$repo/scripts/check.sh"; }
refuse() {
  local diagnostic=$1
  shift
  if "$@" >"$scratch/log" 2>&1; then printf 'Expected failure for %s\n' "$diagnostic" >&2; return 1; fi
  grep -F -- "$diagnostic" "$scratch/log" || { cat "$scratch/log"; return 1; }
}
snapshot() {
  (cd "$scratch/tree" && find . -path './.git' -prune -o -type f -print0 | sort -z | xargs -0 sha256sum)
}
cat >"$scratch/tree/play.yml" <<'YAML'
---
- name: Check fixture
  hosts: all
  gather_facts: false
  vars:
    message: synthetic
  tasks:
    - name: Report fixture
      ansible.builtin.debug:
        msg: "{{ message }}"
YAML
git -C "$scratch/tree" add -- play.yml
before=$(snapshot)
check
test "$(snapshot)" = "$before"
cp -- "$scratch/tree/play.yml" "$scratch/play.yml"
sed -i 's/{{ message }}/{{message}}/' "$scratch/tree/play.yml"
(cd "$scratch/tree"; "${ANSIBLE_CI_PYTHON%/*}/ansible-lint" --offline --profile production play.yml) >"$scratch/native" 2>&1
grep -F 'jinja[spacing]' "$scratch/native"
refuse 'jinja[spacing]' check
cp -- "$scratch/play.yml" "$scratch/tree/play.yml"
sed -i 's/ansible.builtin.debug/debug/' "$scratch/tree/play.yml"
refuse 'fqcn[action-core]' check
cat >"$scratch/tree/.ansible-lint" <<'YAML'
---
exclude_paths:
  - play.yml
YAML
git -C "$scratch/tree" add -- .ansible-lint
refuse 'exclude_paths' check
git -C "$scratch/tree" rm -q -f -- .ansible-lint
sed -i 's/debug/nonexistent.missing.action/' "$scratch/tree/play.yml"
refuse 'syntax-check' check
cp -- "$scratch/play.yml" "$scratch/tree/play.yml"
refuse 'profile' env ANSIBLE_CI_PROFILE=invented "$repo/scripts/check.sh"
refuse 'escapes the checkout' env ANSIBLE_CI_WORKING_DIRECTORY=.. "$repo/scripts/check.sh"
mkdir "$scratch/tree/empty"
refuse 'No Ansible content' env ANSIBLE_CI_WORKING_DIRECTORY=empty "$repo/scripts/check.sh"

printf '%s\n' 'plugin: community.synthetic.dynamic' >"$scratch/tree/inventory.yml"
git -C "$scratch/tree" add -- inventory.yml
refuse 'static YAML or INI inventory' env ANSIBLE_CI_FIXTURE_INVENTORY=inventory.yml "$repo/scripts/check.sh"
git -C "$scratch/tree" rm -q -f -- inventory.yml

mkdir -p "$scratch/collection/plugins/modules" "$scratch/tree/ci"
cat >"$scratch/collection/galaxy.yml" <<'YAML'
---
namespace: synthetic
name: fixture
version: 1.0.0
readme: README.md
authors: [Synthetic fixture]
YAML
printf '# Synthetic fixture\n' >"$scratch/collection/README.md"
printf '# A module used for syntax resolution only.\n' >"$scratch/collection/plugins/modules/proof.py"
"${ANSIBLE_CI_PYTHON%/*}/ansible-galaxy" collection build "$scratch/collection" --output-path "$scratch/tree/ci"
archive=ci/synthetic-fixture-1.0.0.tar.gz
digest=$(sha256sum "$scratch/tree/$archive")
cat >"$scratch/tree/ci/ansible-content.lock" <<YAML
dependencies:
  - kind: collection
    archive: $archive
    version: "1.0.0"
    sha256: "${digest%% *}"
YAML
sed -i 's/ansible.builtin.debug:/synthetic.fixture.proof: {}/; /        msg: /d' "$scratch/tree/play.yml"
git -C "$scratch/tree" add -- ci
check
printf 'corrupt\n' >"$scratch/tree/$archive"
refuse 'checksum' check
