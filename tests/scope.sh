#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
case_name=${1:?Fixture required}
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
cd "$scratch"
git init -q
export ANSIBLE_CI_WORKSPACE="$scratch"
export ANSIBLE_CI_CHECK="$repo/scripts/check.sh"
hook="$repo/examples/native-hook/.githooks/pre-commit"
commit_fixture() {
  git add -- "$@"
  git -c user.name='Synthetic fixture' -c user.email=fixture@example.invalid commit -q -m fixture
}
refuse() {
  local diagnostic=$1
  shift
  if "$@" >"$scratch/fixture.log" 2>&1; then
    printf 'Expected refusal: %s\n' "$diagnostic" >&2
    return 1
  fi
  grep -F -- "$diagnostic" "$scratch/fixture.log" || { cat "$scratch/fixture.log"; return 1; }
}
cat >play.yml <<'YAML'
---
- name: Run fixture
  hosts: all
  gather_facts: false
  tasks:
    - name: Report fixture
      ansible.builtin.debug:
        msg: "synthetic"
YAML
case "$case_name" in
  malformed)
    sed '/  hosts: all/d' play.yml > broken.yml
    commit_fixture play.yml broken.yml
    refuse 'syntax-check' "$ANSIBLE_CI_CHECK"
    ;;
  metadata)
    sed 's/ansible.builtin.debug/debug/' play.yml > existing-bad.yml
    commit_fixture play.yml existing-bad.yml
    printf '%s\n' 'release_name: synthetic' > metadata.yml
    git add -- metadata.yml
    "$hook"
    ;;
  inventory)
    printf '[fixture]\nlocalhost ansible_connection=local\n' > fixture.ini
    commit_fixture play.yml fixture.ini
    export ANSIBLE_CI_FIXTURE_INVENTORY=fixture.ini
    "$ANSIBLE_CI_CHECK"
    printf '#!/usr/bin/env sh\nexit 0\n' > fixture.ini
    git add -- fixture.ini
    refuse 'static YAML or INI inventory' "$hook"
    refuse 'static YAML or INI inventory' "$ANSIBLE_CI_CHECK" --staged
    ;;
  role)
    mkdir -p ci archive/fixture_role/{meta,tasks}
    printf '%s\n' '---' 'dependencies: []' > archive/fixture_role/meta/main.yml
    printf '%s\n' '---' '- name: Report fixture' '  ansible.builtin.debug:' '    msg: "synthetic"' > archive/fixture_role/tasks/main.yml
    tar -czf ci/fixture_role-1.0.0.tar.gz -C archive fixture_role
    checksum=$(sha256sum ci/fixture_role-1.0.0.tar.gz)
    cat >ci/ansible-content.lock <<YAML
dependencies:
  - kind: role
    archive: ci/fixture_role-1.0.0.tar.gz
    version: "1.0.0"
    sha256: "${checksum%% *}"
YAML
    cat >play.yml <<'YAML'
---
- name: Verify the locked fixture role
  hosts: all
  gather_facts: false
  roles:
    - fixture_role
YAML
    commit_fixture play.yml ci
    "$ANSIBLE_CI_CHECK"
    ;;
  *) printf 'Unknown fixture: %s\n' "$case_name" >&2; exit 1 ;;
esac
