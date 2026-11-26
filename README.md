# Ansible CI action

Check roles and playbooks on Linux x64 with strict production-profile
ansible-lint and its syntax check. Lint runs on a temporary copy of tracked
files with a synthetic inventory and isolated configuration. Use local
verification on trusted checkouts because Ansible content can contain plugins.

## GitHub Actions

Checkout the caller repository with credential persistence disabled, then use
`vhco-pro/ansible-ci-action` at a full released commit SHA. The
[fixture workflow](.github/workflows/test.yml) exercises the action by path.
Set contents permission to read and use Ubuntu 24.04 x64.

| Input | Default |
| --- | --- |
| `working-directory` | `.` within the checkout. |
| `profile` | `production`. |
| `fixture-inventory` | An isolated localhost inventory. An override names a tracked static YAML or INI fixture file relative to the checkout. |

Outputs are `python-version`, `ansible-core-version`, and `ansible-lint-version`.
The action reads standard lint config files in the selected scope and its
ancestors. It refuses ignore entries and config options that can suppress checks.

If syntax checks need external Ansible content, include a tracked
`ci/ansible-content.lock` in the checkout. Each entry in its `dependencies` list
names a `kind` of `role` or `collection`, a checkout-relative `archive` path,
an exact `version`, and the archive's `sha256`. Supply the locked archives and
their transitive dependencies. Role archives use one top-level directory
whose name is the installed role name. Archives can contain regular files and
directories. Setup verifies hashes and installs locally with dependency fetching
disabled.

## Local check and hook

Run `scripts/setup.sh install DESTINATION` from a pinned checkout of this
action. Set `ANSIBLE_CI_PYTHON` to `DESTINATION/venv/bin/python`, then run
the pinned `scripts/check.sh` from the caller checkout. Optional environment
settings are `ANSIBLE_CI_WORKING_DIRECTORY`, `ANSIBLE_CI_PROFILE`, and
`ANSIBLE_CI_FIXTURE_INVENTORY`.

Copy [the native hook](examples/native-hook/.githooks/pre-commit) to
`.githooks/pre-commit` and set the repo-local `core.hooksPath` to `.githooks`
after checking for existing hooks. Set `ANSIBLE_CI_CHECK` to the pinned check
script and point it at the prepared Python environment. The hook uses the Git
index, follows literal task imports and skips unrelated changes. Run full verification before pushing.

For diagnosis in the prepared environment with synthetic inventory:

```sh
ansible-lint --offline --strict --profile production
ansible-playbook --syntax-check -i fixtures/inventory.yml playbook.yml
ansible-doc ansible.builtin.copy
```

Where role behavior needs execution, the consumer can run
`molecule test -s SCENARIO` against a disposable target and assert convergence,
idempotence and the resulting behavior. Live playbooks and deployment belong
to a separate authorized workflow.

## Maintainer checks

With the pinned environment, run `tests/setup.sh`, `tests/check.sh`,
`tests/hook.sh`, `tests/release.sh`, and `actionlint`. Regenerate
`scripts/requirements.txt` with wheel hashes for the pinned Python when
updating controller dependencies. For a Python version update, verify the
upstream build and archive digest, update `scripts/python-archive.tsv` alongside
`scripts/.tool-versions`, and regenerate the lock for the new Python version.

## Security checks

CodeQL scans the GitHub Actions files and Python source. ShellCheck checks the Bash scripts
and the native Git hook. OpenSSF Scorecard runs on the public default branch.
