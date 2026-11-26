---
status: draft
status_description: "Owner-approved design captured for independent specification review."
issue: null
goal: "Consumers can run the same production-profile Ansible checks locally and in GitHub Actions."
covers:
  - action.yml
  - scripts/
  - tests/
  - examples/
  - .github/workflows/
  - README.md
  - LICENSE
---

# Ansible CI action

## Context

### Owner summary

One action checks Ansible content with a pinned controller and the production lint profile on Linux x64. The same check script runs locally. A native Git hook example can check the staged version of affected roles or playbooks after their dependencies are installed. Functional Molecule scenarios stay with the caller.

Public fixtures exercise clean content, lint findings and syntax errors without an infrastructure target. The action starts on its own implementation branch. Release and consumer rollout need separate approval.

### Background

The shared convention at [4635f7e](https://github.com/vhco-pro/docs/blob/4635f7e12f7a8d9b24046ef943bc382b0d74dff1/conventions/terraform-ansible.md) uses production-profile lint and syntax checking, with isolated functional scenarios where useful. A local probe with `ansible-playbook` core 2.18.18rc1 accepted a synthetic localhost playbook and refused one naming a missing collection action. This proves the syntax fixture behavior on that installed runtime. It precedes action, production-profile and pinned dependency verification.

## Scope

Deliver one composite, its direct check script, native Git hook example, public synthetic fixtures and shared release wiring. Support Ubuntu 24.04 x64 on GitHub and Linux x64 locally. Keep real playbook runs, private repositories and deploys outside this feature.

## Design

- Inputs are `working-directory` (default `.`), `profile` (default `production`) and optional `fixture-inventory`. Use standard project lint configuration discovery. Non-default profiles are for scoped compatibility with documented existing baselines. Reject unknown profiles, empty content scope, and out-of-checkout paths. Keep inventory synthetic and static.
- Use a pinned Python release and hash-locked Python packages for `ansible-core` and `ansible-lint`. Install approved pinned roles and collections in a temporary environment when syntax checking requires them. Use verified archive downloads, expose the resolved `python-version`, `ansible-core-version` and `ansible-lint-version` via `GITHUB_OUTPUT`, and fail on dependency errors. Keep pins discoverable to the dependency updater.
- Run `ansible-lint --offline --profile production` by default with unskipped syntax validation. Scope the runtime to fixture inventory with isolated tool state and no deployment credentials. Document the direct `ansible-playbook --syntax-check -i <fixture-inventory> <playbook>` command. Document `ansible-doc` for installed module contracts.
- Both the composite and caller verification use the same shell script. Provide a native pre-commit example that checks the index snapshot with prepared dependencies. Full local verification can call caller-owned Molecule scenarios for convergence, idempotence and behavior assertions on disposable targets.
- A callable public fixture workflow tests the action and direct verdict on Ubuntu 24.04 with read-only contents permission and disabled checkout credential persistence. Use the shared exact-tag release workflow after successful fixture tests. Pin external `uses:` references by full commit SHA and tag comment. Keep publication permissions confined to the release job.

## Acceptance Criteria

- [ ] AC-01: Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures and empty scopes fail.
- [ ] AC-02: The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, escaping path or failed setup.
- [ ] AC-03: The direct command and native hook share validation behavior. Hook checks use staged content and preserve the source and index.
- [ ] AC-04: The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.

## Test Plan

| Criterion | Proof |
| --- | --- |
| AC-01 | Run `tests/check.sh` with a clean playbook, a lint-only violation, a missing module and an empty directory. Assert the expected exit and specific finding for each failure. Compare tracked inputs before and after. |
| AC-02 | Run `tests/setup.sh` with an exact lock and a corrupted hash. Run `tests/check.sh` with an unknown profile and an out-of-checkout path. The callable workflow verifies reported versions against the installed CLI. |
| AC-03 | Run `tests/hook.sh` in a disposable Git repository with a clean working copy and failing staged playbook, then with a clean staged playbook and failing working copy. Confirm the index and source are unchanged. |
| AC-04 | Lint workflows and examples using `actionlint`. Inspect the release gate and run the public fixture workflow when a feature push is approved. Report hosted and local evidence separately. |

## Tasks

None yet. Tasks are populated after the specification gate.

## Open Questions

None.

## Review Log

| Date | Review | Kind | Commit | Model | Isolation | Outcome |
| --- | --- | --- | --- | --- | --- | --- |

## Sources

- [Ansible-lint production profile](https://docs.ansible.com/projects/lint/profiles/) and [syntax-check rules](https://docs.ansible.com/projects/lint/rules/syntax-check/) describe the default gate.
- [AI Forge write-content](https://github.com/ansible-community/ai-forge/blob/28a9a580b19e208e4c1bbd6146aa60e8aafe8a9f/ansible-content-development/module/skills/write-content/SKILL.md) describes authoring content. [AI Forge write-content-tests](https://github.com/ansible-community/ai-forge/blob/28a9a580b19e208e4c1bbd6146aa60e8aafe8a9f/ansible-content-development/module/skills/write-content-tests/SKILL.md) and [Molecule role testing](https://docs.ansible.com/projects/molecule/getting-started-roles/) describe functional fixtures. [Ansible DevTools](https://ansible.github.io/vscode-ansible/ai/skills/) lists upstream authoring skills.
- [PowerShell fixture workflow](https://github.com/vhco-pro/pwsh-ci-action/blob/v0.1.1/.github/workflows/test.yml) demonstrates checking direct and composite verdicts. [GitHub release workflow](https://github.com/vhco-pro/gh-release-workflow/blob/b18de6d2f305f971afe01ba31e17bde5966b1567/.github/workflows/gh-release.yml) owns GitVersion tagging and publication.
