#!/usr/bin/env bash
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $# -eq 0 ]]; then
  for fixture in malformed metadata metadata-list yaml-stream inventory role staged-archive nested-ignore imported-task handler-only alternate-task unrelated-invalid-yaml referenced-vars; do
    "$0" "$fixture"
  done
  exit 0
fi
case_name=$1
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
  metadata-list)
    sed 's/ansible.builtin.debug/debug/' play.yml > existing-bad.yml
    commit_fixture play.yml existing-bad.yml
    mkdir docs
    printf '%s\n' '- ticket: "DOC-123"' '  summary: "Unrelated metadata"' > docs/catalog.yml
    git add -- docs/catalog.yml
    "$hook"
    ;;
  yaml-stream)
    printf '%s\n' '---' 'ticket: "DOC-123"' '---' 'ticket: "DOC-124"' > catalog.yml
    commit_fixture play.yml catalog.yml
    "$ANSIBLE_CI_CHECK"
    ;;
  nested-ignore)
    mkdir -p ansible/.config
    mv -- play.yml ansible/play.yml
    commit_fixture ansible/play.yml
    export ANSIBLE_CI_WORKING_DIRECTORY=ansible
    printf 'play.yml fqcn[action-core]\n' > ansible/.config/ansible-lint-ignore.txt
    git add -- ansible/.config/ansible-lint-ignore.txt
    refuse 'Lint ignore entries are unsupported' "$hook"
    ;;
  imported-task)
    sed -i '/    - name: Report fixture/,$d' play.yml
    printf '%s\n' '    - name: Load fixture task' '      ansible.builtin.import_tasks: setup.yml' >> play.yml
    printf '%s\n' '---' '- name: Report fixture' '  ansible.builtin.debug:' '    msg: "synthetic"' > setup.yml
    commit_fixture play.yml setup.yml
    "$ANSIBLE_CI_CHECK"
    sed -i 's/ansible.builtin.debug/debug/' setup.yml
    git add -- setup.yml
    refuse 'fqcn[action-core]' "$ANSIBLE_CI_CHECK"
    index=$(git write-tree)
    refuse 'fqcn[action-core]' "$hook"
    refuse 'fqcn[action-core]' "$ANSIBLE_CI_CHECK" --staged
    test "$index" = "$(git write-tree)"
    ;;
  handler-only)
    rm -- play.yml
    mkdir -p roles/handler_only/handlers
    handler=roles/handler_only/handlers/main.yml
    cat >"$handler" <<'YAML'
---
- name: Report fixture
  ansible.builtin.debug:
    msg: synthetic
YAML
    commit_fixture "$handler"
    export ANSIBLE_CI_WORKING_DIRECTORY=roles/handler_only
    "$ANSIBLE_CI_CHECK"
    sed -i 's/ansible.builtin.debug/debug/' "$handler"
    git add -- "$handler"
    refuse 'fqcn[action-core]' "$ANSIBLE_CI_CHECK"
    refuse 'fqcn[action-core]' "$hook"
    ;;
  alternate-task)
    rm -- play.yml
    mkdir -p roles/alternate_task/tasks
    task=roles/alternate_task/tasks/configure.yml
    cat >"$task" <<'YAML'
---
- name: Report fixture
  ansible.builtin.debug:
    msg: synthetic
YAML
    commit_fixture "$task"
    export ANSIBLE_CI_WORKING_DIRECTORY=roles/alternate_task
    "$ANSIBLE_CI_CHECK"
    sed -i 's/ansible.builtin.debug/debug/' "$task"
    git add -- "$task"
    refuse 'fqcn[action-core]' "$hook"
    ;;
  unrelated-invalid-yaml)
    mkdir docs
    printf '%s\n' 'unfinished: [' > docs/example.yml
    commit_fixture play.yml docs/example.yml
    printf '# Unrelated edit\n' > README.md
    git add -- README.md
    index=$(git write-tree)
    "$hook"
    test "$index" = "$(git write-tree)"
    printf '%s\n' '  tasks: [' >> play.yml
    git add -- play.yml
    refuse 'expected the node content' "$hook"
    ;;
  referenced-vars)
    sed -i '/  tasks:/i\  vars_files: [variables.json]' play.yml
    printf '%s\n' '{"message": "synthetic"}' > variables.json
    commit_fixture play.yml variables.json
    "$ANSIBLE_CI_CHECK"
    printf '%s\n' '{"message": "updated"}' > variables.json
    git add -- variables.json
    index=$(git write-tree)
    "$ANSIBLE_CI_CHECK" --staged >"$scratch/verify.log" 2>&1
    grep -F '1 files processed' "$scratch/verify.log"
    "$hook" >"$scratch/verify.log" 2>&1
    grep -F '1 files processed' "$scratch/verify.log"
    test "$index" = "$(git write-tree)"
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
  role|staged-archive)
    package_dir=ci
    if [[ $case_name == staged-archive ]]; then package_dir=vendor; fi
    mkdir -p ci "$package_dir" archive/fixture_role/{meta,tasks}
    package="$package_dir/fixture_role-1.0.0.tar.gz"
    printf '%s\n' '---' 'dependencies: []' > archive/fixture_role/meta/main.yml
    printf '%s\n' '---' '- name: Report fixture' '  ansible.builtin.debug:' '    msg: "synthetic"' > archive/fixture_role/tasks/main.yml
    tar -czf "$package" -C archive fixture_role
    checksum=$(sha256sum "$package")
    cat >ci/ansible-content.lock <<YAML
dependencies:
  - kind: role
    archive: $package
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
    commit_fixture play.yml ci "$package"
    "$ANSIBLE_CI_CHECK"
    if [[ $case_name == staged-archive ]]; then
      printf 'synthetic corruption\n' > "$package"
      git add -- "$package"
      index=$(git write-tree)
      refuse 'checksum mismatch' "$hook"
      refuse 'checksum mismatch' "$ANSIBLE_CI_CHECK" --staged
      test "$index" = "$(git write-tree)"
    fi
    ;;
  *) printf 'Unknown fixture: %s\n' "$case_name" >&2; exit 1 ;;
esac
