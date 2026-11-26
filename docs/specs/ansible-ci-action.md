---
status: complete
status_description: "Implementation and independent fixture review are complete."
branch: feat/ansible-ci-action
issue: https://github.com/vhco-pro/ansible-ci-action/issues/1
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

One action checks Ansible content with a pinned controller and the production lint profile on Linux x64. The same check script runs locally. A native Git hook example checks affected roles or playbooks from the Git index after their dependencies are installed. The action runs syntax checks against synthetic inventory in an isolated configuration and process environment. Functional Molecule scenarios stay with the caller.

Public fixtures exercise clean content, lint findings and syntax errors without an infrastructure target. The action starts on its own implementation branch. Release and consumer rollout need separate approval.

### Background

Maintainers of multiple Ansible repositories would otherwise repeat the controller pins, lint configuration and GitHub permission rules in each repo. Carrying those rules in one action with a native local command gives a common verdict and one toolchain update path.

The shared convention at [4635f7e](https://github.com/vhco-pro/docs/blob/4635f7e12f7a8d9b24046ef943bc382b0d74dff1/conventions/terraform-ansible.md) uses production-profile lint and syntax checking, with isolated functional scenarios where useful. A local probe with `ansible-playbook` core 2.18.18rc1 accepted a synthetic localhost playbook and refused one naming a missing collection action. This proves the syntax fixture behavior on that installed runtime. It precedes action, production-profile and pinned dependency verification.

## Scope

Deliver one composite, its direct check script, native Git hook example, public synthetic fixtures and shared release wiring. Support Ubuntu 24.04 x64 on GitHub and Linux x64 locally. Keep real playbook runs, private repositories and deploys outside this feature.

## Design

- Inputs are `working-directory` (default `.`), `profile` (default `production`) and optional `fixture-inventory`. Discover the project lint configuration with the native config names. Use the requested profile explicitly and fail closed on config or ignore-file entries that suppress or exclude checks in the selected scope. Existing code can adopt the action by selecting the covered paths under its recorded baseline. Resolve selected playbooks and roles explicitly and refuse an empty set, unknown profile, or out-of-checkout path. The default inventory is synthetic localhost. An override must be a checkout-relative static YAML or INI fixture file. Reject dynamic inventory and inventory plugin configuration.
- Use a pinned Python release and hash-locked Python packages for `ansible-core` and `ansible-lint`. For content dependencies, use a checkout-relative `ci/ansible-content.lock` when present. It lists each required local role or collection archive with an exact version and SHA-256, including transitive dependencies. Install the verified archives in private temporary directories with dependency fetching disabled. Missing or invalid required archives fail, and failed setup cleans up its temporary state. Use verified archive downloads, expose the resolved `python-version`, `ansible-core-version` and `ansible-lint-version` via `GITHUB_OUTPUT`, and fail on dependency errors. Keep pins discoverable to the dependency updater.
- Run `ansible-lint --offline --strict --profile production` by default with unskipped syntax validation. Strict mode makes warnings in the selected profile block the check. Run the linter and inherited syntax subprocess with an allowlisted process environment, run-owned HOME, explicit generated Ansible config, and only the static YAML and INI inventory plugins. Keep the operator's Ansible config, inventory, plugin settings and credentials out of those processes. Use local verification for trusted checkouts because project content can include executable plugins. Document the direct `ansible-playbook --syntax-check -i <fixture-inventory> <playbook>` command. Document `ansible-doc` for installed module contracts.
- Both the composite and caller verification use the same shell script. Provide a native pre-commit example that checks affected roles or entry-point playbooks from the index snapshot with prepared dependencies. An unrelated staged change skips lint. A change to shared configuration, inventory, content locks or dependencies selects every Ansible scope affected by it. Full local verification can call caller-owned Molecule scenarios for convergence, idempotence and behavior assertions on disposable targets.
- A callable fixture workflow runs on Ubuntu 24.04 with read-only contents permission and disabled checkout credential persistence. SHA-pin external actions with release comments. A default-branch push can call the shared GitVersion workflow after the fixtures pass. Pull requests run the fixtures with read-only permissions. Manual recovery accepts only an existing exact stable version tag that resolves to the tested commit. After the same fixture gate, recovery calls the shared GitHub Release action for that exact tag. Serialize publication across push and recovery runs and preserve existing releases.

## Acceptance Criteria

- [x] AC-01: Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
      Evidence: R-12 confirmed native production lint and syntax, including handler-only and alternate task entries.
- [x] AC-02: The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
      Evidence: R-12 confirmed the versions, composite verdicts, checksum refusals and isolation in public run 45859953475 and native tests.
- [x] AC-03: The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
      Evidence: R-12 confirmed the hook skips unrelated edits, detects referenced files and still rejects malformed selected role inputs.
- [x] AC-04: The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
      Evidence: R-12 confirmed public run 45859953475, actionlint and the release gate tests.

## Test Plan

| Criterion | Proof |
| --- | --- |
| AC-01 | Run `tests/check.sh` with a clean playbook, a lint-only violation, a missing module, an empty directory and config with a suppression or exclusion covering the violation. A playbook with an otherwise clean task and unspaced Jinja interpolation passes native non-strict lint with a `jinja[spacing]` warning and fails with that diagnostic through the strict check. Assert the expected status and diagnostic for each failure. Compare tracked inputs before and after. |
| AC-02 | Run `tests/setup.sh` with an exact Python lock and a corrupt hash. A playbook using a synthetic locked collection must pass, then fail when its archive is missing or corrupt. Run `tests/check.sh` with an unknown profile, an out-of-checkout path and a dynamic inventory fixture. A subprocess test asserts the use of controlled configuration and synthetic localhost inventory and the absence of an ambient credential sentinel. The callable workflow verifies reported versions against the installed CLI. |
| AC-03 | Run `tests/hook.sh` in a disposable Git repository with a clean working copy and failing staged playbook, then with a clean staged playbook and failing working copy. Verify an unrelated stage skips lint and a shared configuration change selects all affected scopes. Confirm the index and source are unchanged. |
| AC-04 | Lint workflows and examples with `actionlint`. Test the release gate on synthetic Git refs: default-branch push after passing fixtures and an existing exact stable recovery tag at the tested commit are eligible; PRs, failing fixtures, branches on dispatch, and a tag pointing to another commit cannot publish. Hosted fixture evidence remains separate from local checks. |

## Tasks

- [x] T1 `tests/setup.sh`, `tests/check.sh`, `tests/hook.sh`, and `tests/release.sh` specify clean and refusal cases. See each fail because its entry point is absent (AC-01, AC-02, AC-03, AC-04).
      Evidence: Each test failed at its absent setup, check, hook, or release entry point.
- [x] T2 `scripts/setup.sh` and tool pins install the verified Python and lint packages. Run `tests/setup.sh` (AC-02).
      Evidence: tests/setup.sh installed the pinned Python and hashed wheels and refused both an incorrect archive checksum and corrupted wheel hashes.
- [x] T3 `scripts/check.sh` validates lint scope, fixture inventory and content locks. Run `tests/check.sh` (AC-01, AC-02).
      Evidence: tests/check.sh passed production-profile checks, syntax failures, scope and inventory refusals, credential isolation and locked collection checks.
- [x] T4 `examples/native-hook/` invokes the check on staged affected content. Run `tests/hook.sh` (AC-03).
      Evidence: tests/hook.sh exercised partial staging, ignored unrelated changes and checked all affected playbooks on a config change.
- [x] T5 `action.yml`, `.github/workflows/`, and `README.md` wire the fixture and release jobs. Run `tests/release.sh` and `actionlint`. Observe the composite on a public runner when authorized (AC-02, AC-04).
      Evidence: actionlint, the release ref gate fixtures and direct pass and warning-only refusal cases passed locally with actual version outputs. Hosted composite execution remains pending.

- [x] T6 `scripts/check.py`, the native hook and scope fixtures check malformed plays, locked roles and relevant staged dependencies. Run `tests/scope.sh` and the native check and hook suites (AC-01, AC-02, AC-03).

      Evidence: The four scope fixtures failed before the fixes. All four passed after the fixes, along with the native check, staged hook, release guard and actionlint.

- [x] T7 `scripts/check.py`, the native hook and scope fixtures use staged lock paths and distinguish unrelated YAML documents. Run native scope, hook and check suites (AC-01, AC-03).

      Evidence: The unrelated YAML list and stream, staged archive outside ci/, and nested ignore-file fixtures failed before the change and passed after it. Native, hook, release and actionlint suites passed.

- [x] T8 `scripts/check.py` and `tests/scope.sh` select staged files referenced by literal imports. Verify the imported task refusal and the unrelated YAML allowance (AC-03).

      Evidence: The imported-task fixture passed outside the hook and then showed the missing staged refusal. After repair, both paths refused the short module name. Scope, check, hook, release and lint suites passed.

- [x] T9 `scripts/check.py` and the native hook discover handler-only roles and select staged files referenced by a playbook regardless of suffix. Add regressions for both and check that unrelated edits still skip lint (AC-01, AC-03).
      Evidence: The handler-only role and staged JSON variable file regressions first failed against the prior code. The full native check, scope and hook suites passed after the fix, including the unrelated Markdown edit and preservation of the index.

- [x] T10 `scripts/check.py` and the scope fixtures cover role directories with alternate task files and skip parsing unrelated staged content as Ansible (AC-01, AC-03).
      Evidence: The alternate task entry and unrelated invalid YAML fixtures failed before the change. The same fixtures and the full native check, scope, and hook suites passed after the change. A malformed staged playbook still failed.

- [x] T11 `scripts/check.py` and the staged scope fixture tolerate an unfinished role file during reference discovery for unrelated stages (AC-03).
      Evidence: The README-only fixture failed before the change. It passed afterward and the same fixture still rejected the unfinished role when a file in that role was staged. The full native check, hook and scope suites passed.

## Open Questions

None.

## Review Log

| Date | Review | Kind | Commit | Model | Isolation | Outcome |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-11-26 | R-1 | spec | `d5bd9419c917b29030e37cf74d42c7a5b7a9abcd` | unknown | procedural | Inventory isolation and selected lint scope need explicit tests. |
| 2026-11-26 | R-2 | spec | `f6b110f692c5d18ceb9078232707429e9a2d37c5` | unknown | procedural | Production-profile warnings must fail. |
| 2026-11-26 | R-3 | spec | `d6d0e63d36caf35ca942b8f3f52b7e35e4d86481` | unknown | procedural | The warning fixture must match the action's lint scope. |
| 2026-11-26 | R-4 | spec | `6199a51ae0db55326f5e33bc320ce1d1e0938847` | unknown | procedural | No findings. |
| 2026-11-26 | R-4 | spec | `6199a51ae0db55326f5e33bc320ce1d1e0938847` | n/a | n/a | accepted by owner |
| 2026-11-26 | R-5 | implementation | `0c8d87655b95c801ded036e6f717244d55ddf926` | unknown | procedural | Playbook selection, staged scope and local role archives need fixes. |
| 2026-11-26 | R-6 | implementation | `332d1b9c00959571a22062490717d0a792c8c8bd` | unknown | procedural | Unrelated YAML and staged locked archives need fixes. |
| 2026-11-26 | R-7 | implementation | `aebe22dddaece8190b838f35e1f1c2a5fdf9b9ed` | unknown | procedural | The staged scope missed a literal import. |
| 2026-11-26 | R-8 | implementation | `b25012384abe82fe8c15d06aeb81eaee086cdeef` | unknown | procedural | Native criteria met. Hosted execution pending. |
| 2026-11-26 | R-9 | implementation | `e661aefe97563d77e84fba53d02b09d0fd378937` | unknown | procedural | Hosted fixtures passed. Role discovery and staged variable files need fixes. |
| 2026-11-26 | R-10 | implementation | `8a60b5e3f9448b34dddac071bf2e7ff4b5c2b0dd` | unknown | procedural | Hosted fixtures passed. Alternate role entries and unrelated staged edits need fixes. |
| 2026-11-26 | R-11 | implementation | `a7e80a8073b3692fe2ff09ff86814d268dd8d4d8` | unknown | procedural | Three criteria met. An unfinished role file still blocks an unrelated staged edit. |
| 2026-11-26 | R-12 | implementation | `cdafd6932e926c606ef829dc7888b10a4d472487` | unknown | procedural | All four criteria met. Python archive updates still require manual review. |
| 2026-11-26 | R-13 | implementation | `4d5b84fd2ced82e9870591cb93fbed2e75bef23c` | unknown | procedural | All four criteria met. Public security onboarding findings are recorded below. |
| 2026-11-26 | R-14 | implementation | `2b8efa933b9f4e55591a626c4c159ad2e8349e71` | unknown | procedural | All four criteria met. Shared security workflow findings remain open. |
| 2026-11-26 | R-15 | implementation | `78bf1dcaa075590a7e5ca8f98ebd7bf26bb1ec9e` | unknown | procedural | All criteria met with the released CodeQL pin. |

### R-1

FINDING: F-01
KIND: factual
SEVERITY: blocking
WHERE: Owner summary, Scope, Design inputs and lint invocation, AC-02, AC-03, AC-04, Test Plan
EVIDENCE: The design leaves `fixture-inventory` optional and allows normal configuration discovery, but does not specify how the syntax subprocess is prevented from loading the project or operator's inventory and plugin settings. Ansible's default inventory plugins include `script` and `auto`, and ansible-lint documents `--offline` as disabling dependency installation and schema refreshing. It does not isolate subprocesses. The shared coding convention requires an allowlisted environment for user-supplied code. https://docs.ansible.com/projects/ansible/latest/plugins/inventory.html https://docs.ansible.com/projects/lint/configuring/
PROPOSAL: Define a default synthetic inventory, the allowed static inventory formats, and an explicit isolated Ansible configuration and environment for all entry points. Add a refusal test for dynamic inventory and prove the syntax subprocess does not receive ambient credentials or operator configuration.

FINDING: F-02
KIND: factual
SEVERITY: blocking
WHERE: Owner summary, Design default profile and configuration discovery, AC-01, Test Plan AC-01
EVIDENCE: AC-01 says production-rule violations and syntax failures fail. The design permits standard configuration discovery, and ansible-lint documents that `warn_list`, `skip_list`, `exclude_paths`, and the adjacent ignore file can alter those verdicts. Syntax check is unskippable for a playbook that is linted, but the config can exclude the playbook entirely. The clean and negative fixtures in the proof leave this conflict untested. https://docs.ansible.com/projects/lint/configuring/ https://docs.ansible.com/projects/lint/rules/syntax-check/
PROPOSAL: Define which narrowly recorded compatibility exceptions may change a verdict and how the wrapper prevents a selected scope from being silently excluded. Use a fixture with configuration overrides to prove the accepted boundary.

FINDING: F-03
KIND: factual
SEVERITY: should-fix
WHERE: Design pinned dependencies, AC-02, Test Plan AC-02
EVIDENCE: The design calls for installing approved pinned roles and collections when syntax needs them, but all three declared inputs concern scope, profile or inventory. It gives no source for the approved dependency set, no rule for transitive dependencies, and no expected behavior on a partial installation. The proposed corrupted-hash test can pass for the Python lock alone without exercising any Ansible content dependencies.
PROPOSAL: Specify the dependency manifest or prepared dependency interface, how it pins transitive content, and how a failed setup discards partial state. Add a content fixture whose syntax succeeds with the locked dependency and fails when it is absent.

FINDING: F-04
KIND: factual
SEVERITY: should-fix
WHERE: Design staged hook, AC-03, Test Plan AC-03
EVIDENCE: The owner summary promises checks for affected roles or playbooks while the design and proof only require using index content. A hook that scans the full repository on every commit satisfies the written proof, including when no staged path affects Ansible. The pinned infrastructure convention calls for quick checks for relevant staged paths and leaves dependency downloads to full verification.
PROPOSAL: Define the hook's affected-scope rule, including what happens when shared config changes, and add an unrelated-staged-change case that proves it skips lint. Keep the index-versus-worktree cases.

FINDING: F-05
KIND: factual
SEVERITY: should-fix
WHERE: Design shared release wiring, AC-04, Test Plan AC-04
EVIDENCE: The referenced reusable workflow defaults `dry-run` to false and gives its release job `contents: write`. The design does not define caller events, the exact-ref recovery guard, or serialization of publication runs. Inspecting only that tests gate the call can pass a release workflow that also calls it for unsuitable events. https://github.com/vhco-pro/gh-release-workflow/blob/b18de6d2f305f971afe01ba31e17bde5966b1567/.github/workflows/gh-release.yml
PROPOSAL: State the events and refs that may publish, leave pull requests on the fixture path, and specify the exact-tag recovery and concurrency behavior required by the pinned GitHub Actions convention. Check those guards along with `needs` in AC-04.

FINDING: F-06
KIND: factual
SEVERITY: should-fix
WHERE: Context Background
EVIDENCE: Background records a syntax probe and summarizes the convention. It does not say who experiences the problem, how often it recurs, or why a documented native local command and per-repository workflow do not meet the need.
PROPOSAL: Describe the recurring maintenance or verdict drift for consuming repositories and why the reusable action is worth owning alongside the native command.

### R-2

FINDING: F-01
KIND: factual
SEVERITY: blocking
WHERE: Design lint invocation and suppression handling, AC-01, Test Plan AC-01
EVIDENCE: The revision addressing R-1 F-02 rejects suppressions in project configuration and ignore files, but retains `ansible-lint --offline --profile production` without strict mode. Ansible-lint's own default warning list includes `fqcn[deep]`, a subrule of `fqcn` in the production profile. An unconfigured repository can therefore report a production-profile violation and exit zero despite AC-01 requiring failure. A negative fixture that uses a rule already treated as an error would miss this case. https://docs.ansible.com/projects/lint/usage/ https://docs.ansible.com/projects/lint/profiles/
PROPOSAL: Require strict mode so warnings from selected rules fail without relying on project configuration. Add a clean-config fixture that trips a selected rule normally reported as a warning, and verify the wrapper fails on that diagnostic.

### R-3

FINDING: F-01
KIND: factual
SEVERITY: blocking
WHERE: Design explicit lint scope, AC-01, Test Plan AC-01
EVIDENCE: The revision addressing R-2 F-01 adds a nested Python collection plugin as proof of strict mode. The design resolves playbooks and roles as explicit lint targets. Ansible-lint's `fqcn[deep]` rule checks a lintable whose kind is `plugin`. A correct implementation that passes only the specified playbooks and roles to the linter can miss that fixture. https://github.com/ansible/ansible-lint/blob/main/src/ansiblelint/rules/fqcn.py
PROPOSAL: Use a `jinja[spacing]` warning in an otherwise clean playbook, within the existing lint scope. Prove it exits zero with native non-strict lint and fails with the expected diagnostic through the wrapper.

### R-4

NO FINDINGS

### R-5

CRITERION: AC-01 Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
VERDICT: not met
EVIDENCE: At 0c8d87655b95c801ded036e6f717244d55ddf926, `tests/check.sh` passed. In a separate synthetic repository, the pinned `ansible-playbook --syntax-check` exited 4 for a play missing `hosts`. The wrapper exited 0 and reported only one file checked because it selected the valid sibling.

CRITERION: AC-02 The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
VERDICT: not met
EVIDENCE: At 0c8d87655b95c801ded036e6f717244d55ddf926, `tests/setup.sh` independently installed Python 3.14.10, ansible-core 2.22.0 and ansible-lint 26.11.1, then refused both corrupt archive and wheel hashes. `tests/check.sh` passed its collection, input and environment checks. A valid checksum-locked local role archive failed installation before lint. Hosted composite outputs were not observed.

CRITERION: AC-03 The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
VERDICT: not met
EVIDENCE: At 0c8d87655b95c801ded036e6f717244d55ddf926, `tests/hook.sh` passed its partial staging, index preservation and shared configuration tests. A separate inventory-only change passed both the hook and `check.sh --staged` despite the direct command rejecting it. An unrelated staged YAML mapping triggered lint and blocked the commit on an unchanged playbook.

CRITERION: AC-04 The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
VERDICT: not verified
EVIDENCE: At 0c8d87655b95c801ded036e6f717244d55ddf926, actionlint 1.7.12 and `tests/release.sh` passed. The workflows grant fixture jobs read access, disable checkout credential persistence, and put the shared version job behind the fixture gate. Hosted composite execution remains pending authorization.

FINDING: F-01
KIND: factual
SEVERITY: blocking
WHERE: AC-01, scripts/check.py lint_targets
EVIDENCE: The playbook selector at scripts/check.py:71 recognizes `hosts` or `import_playbook`. A tracked sequence containing a named play and `tasks` but missing `hosts` exited 4 in the pinned native syntax checker with `The field 'hosts' is required but was not set.` Alongside a valid playbook, the wrapper exited 0 after checking one file.
PROPOSAL: Select malformed playbook candidates when their structure identifies them as plays even with a required field absent. Add a valid sibling to the regression fixture and require the wrapper to fail on the missing-hosts diagnostic.

FINDING: F-02
KIND: factual
SEVERITY: blocking
WHERE: AC-02, scripts/check.py install_content, README.md content lock
EVIDENCE: A tracked `ci/fixture_role-1.0.0.tar.gz` with valid `meta/main.yml` and `tasks/main.yml` and a matching SHA-256 failed at scripts/check.py:201. The pinned `ansible-galaxy role install` treats the positional absolute archive path as the role name and refuses it as outside the configured role directory. The current setup fixture tests collections only.
PROPOSAL: Generate a role requirement with a validated role name and a separate local archive source. Retain checksum verification and disabled dependency fetching, and test that a playbook can resolve the installed role.

FINDING: F-03
KIND: factual
SEVERITY: should-fix
WHERE: AC-03, examples/native-hook/.githooks/pre-commit, scripts/check.py changed_scopes
EVIDENCE: When only the configured `fixture.ini` was staged, the actual hook and `check.sh --staged` both exited 0. The direct command exited 1 with `fixture-inventory must name a static YAML or INI inventory file.` The hook's filters and staged selector omit the configured INI inventory path.
PROPOSAL: Treat the configured inventory path as a dependency in both hook entry and staged scope selection. Add an inventory-only staged regression test that requires the same verdict as the direct command.

FINDING: F-04
KIND: factual
SEVERITY: should-fix
WHERE: AC-03, examples/native-hook/.githooks/pre-commit, scripts/check.py changed_scopes and select_targets
EVIDENCE: Staging only `metadata.yml` with one unrelated description mapping invoked the actual checker. The hook exited 2 on `fqcn[action-core]` in an unchanged playbook. The shell passes any YAML path and the Python selector falls back to all Ansible targets for a YAML path that is not itself a target.
PROPOSAL: Distinguish Ansible dependencies and candidate lint targets from unrelated YAML before invoking a full-scope check. Add an unrelated YAML fixture with an unchanged failing playbook.

### R-6

CRITERION: AC-01 Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
VERDICT: not met
EVIDENCE: At 332d1b9c00959571a22062490717d0a792c8c8bd, `tests/check.sh` and `tests/scope.sh malformed` passed. A separate synthetic checkout with a clean playbook and a valid, unrelated multi-document YAML file exited 1 before lint with `expected a single document in the stream`.

CRITERION: AC-02 The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
VERDICT: not verified
EVIDENCE: At 332d1b9c00959571a22062490717d0a792c8c8bd, `tests/check.sh` passed the locked collection, invalid input and environment checks. `tests/scope.sh role` installed and resolved the locked role. `scripts/setup.sh versions` reported Python 3.14.10, ansible-core 2.22.0 and ansible-lint 26.11.1. The installer, pins and setup test are unchanged from the prior successful installation and checksum replay. Hosted composite outputs were not observed.

CRITERION: AC-03 The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
VERDICT: not met
EVIDENCE: At 332d1b9c00959571a22062490717d0a792c8c8bd, `tests/hook.sh` and the inventory and metadata scope cases passed. A locked role archive under `vendor/` passed baseline. Staging only corrupt bytes in that archive yielded hook and staged checker exit 0 while the direct checker exited 1 for the checksum mismatch. In a separate checkout, staging only `docs/catalog.yml` containing an unrelated YAML list caused the hook to exit 2 on a lint failure in an unchanged playbook.

CRITERION: AC-04 The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
VERDICT: not verified
EVIDENCE: At 332d1b9c00959571a22062490717d0a792c8c8bd, actionlint 1.7.12 and `tests/release.sh` passed. Workflow inspection confirmed read-only fixture jobs with checkout credentials disabled and a fixture gate before both publication paths. Hosted composite execution remains pending authorization.

FINDING: F-01
KIND: factual
SEVERITY: should-fix
WHERE: AC-03, scripts/check.py changed_scopes, examples/native-hook/.githooks/pre-commit
EVIDENCE: The content lock supports checkout-relative archive paths and the direct action successfully installed a role locked at `vendor/fixture_role-1.0.0.tar.gz`. After staging only corrupt bytes at that path, the hook and staged checker exited 0 and the direct checker exited 1 with `Content archive checksum mismatch: vendor/fixture_role-1.0.0.tar.gz`. The staged selectors do not use the lock's archive paths.
PROPOSAL: Use declared archive paths from the staged lock when determining affected scopes. Add a regression for an archive outside `ci/` and require the hook to refuse the changed checksum.

FINDING: F-02
KIND: factual
SEVERITY: should-fix
WHERE: AC-01 and AC-03, scripts/check.py yaml_keys, lint_targets and select_targets
EVIDENCE: `yaml_keys` applies `yaml.compose` to all visible YAML candidates, so a valid unrelated YAML stream with two documents blocks a clean playbook. For staged changes, any nonempty sequence of mappings triggers the full-scope fallback. Staging only `docs/catalog.yml` containing `- ticket: "DOC-123"` and a summary caused exit 2 on `fqcn[action-core]` in an unchanged playbook.
PROPOSAL: Handle valid multi-document YAML during discovery and distinguish unrelated YAML sequences from Ansible targets and dependencies. Preserve failure behavior for malformed plays and add both unrelated YAML forms to the scope tests.

### R-7

CRITERION: AC-01 Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
VERDICT: met
EVIDENCE: At aebe22dddaece8190b838f35e1f1c2a5fdf9b9ed, `tests/check.sh` passed the clean, strict lint, syntax, suppression and empty-scope cases. `tests/scope.sh malformed`, `yaml-stream` and `nested-ignore` also passed.

CRITERION: AC-02 The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
VERDICT: not verified
EVIDENCE: At aebe22dddaece8190b838f35e1f1c2a5fdf9b9ed, `tests/check.sh` passed the local input, isolation and collection checks. The role and staged archive fixtures passed. `scripts/setup.sh versions` reported Python 3.14.10, ansible-core 2.22.0 and ansible-lint 26.11.1. The installer, package pins and checksum test are unchanged from the previous independent replay. Hosted composite outputs were not observed.

CRITERION: AC-03 The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
VERDICT: not met
EVIDENCE: At aebe22dddaece8190b838f35e1f1c2a5fdf9b9ed, `tests/hook.sh` and all eight scope cases passed. In a separate synthetic checkout, `play.yml` statically imported `setup.yml` using `ansible.builtin.import_tasks`. Staging only a change from `ansible.builtin.debug` to `debug` in `setup.yml` passed the actual hook and `check.sh --staged`. The direct checker exited 2 on `fqcn[action-core]`.

CRITERION: AC-04 The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
VERDICT: not verified
EVIDENCE: At aebe22dddaece8190b838f35e1f1c2a5fdf9b9ed, actionlint 1.7.12 and `tests/release.sh` passed. Workflow inspection confirmed read-only fixture jobs, disabled checkout credential persistence and a fixture gate before publication. Hosted fixture execution was not observed.

FINDING: F-01
KIND: factual
SEVERITY: should-fix
WHERE: AC-03, scripts/check.py looks_like_tasks and select_targets
EVIDENCE: The R-6 YAML relevance fix distinguishes unrelated lists by inspecting keys in the staged file. A referenced `setup.yml` containing a task with a short builtin module name has neither a recognized task key nor a fully qualified key. The selector skips that changed file even though `play.yml` statically imports it. The hook and staged wrapper exit 0 while direct verification exits 2 on the changed task.
PROPOSAL: Recognize literal task references from selected plays when deciding staged relevance. Add an imported task outside the conventional dependency directories to the hook tests and keep the unrelated YAML list case passing.

### R-8

CRITERION: AC-01 Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
VERDICT: met
EVIDENCE: At b25012384abe82fe8c15d06aeb81eaee086cdeef, `tests/check.sh` passed the clean, strict lint, syntax, suppression and empty-scope cases. The malformed play, unrelated YAML stream and nested ignore regressions also passed.

CRITERION: AC-02 The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
VERDICT: not verified
EVIDENCE: At b25012384abe82fe8c15d06aeb81eaee086cdeef, the native input, isolated environment and locked role and collection checks passed. `scripts/setup.sh versions` reported Python 3.14.10, ansible-core 2.22.0 and ansible-lint 26.11.1. The installer, package pins and checksum tests are unchanged from the independently executed setup replay. Hosted composite outputs were not observed.

CRITERION: AC-03 The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
VERDICT: met
EVIDENCE: At b25012384abe82fe8c15d06aeb81eaee086cdeef, `tests/hook.sh` and all nine `tests/scope.sh` cases passed. The literal import case produced the expected lint diagnostic through the direct, staged and hook entry points and verified the index was unchanged. The unrelated YAML, staged inventory, locked archive and partial staging cases passed.

CRITERION: AC-04 The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
VERDICT: not verified
EVIDENCE: At b25012384abe82fe8c15d06aeb81eaee086cdeef, actionlint 1.7.12 and `tests/release.sh` passed. Workflow inspection confirmed read-only fixture jobs with checkout credentials disabled and a fixture gate before either publication path. Hosted fixture execution was not observed.

### R-9

CRITERION: AC-01 Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
VERDICT: not met
EVIDENCE: At e661aefe97563d77e84fba53d02b09d0fd378937, tests/check.sh and tests/scope.sh passed with the pinned toolchain. In a separate tracked fixture, pinned ansible-lint returned 0 for a clean standalone role containing only handlers/main.yml. The wrapper returned 1 with "No Ansible content in working-directory" for that role.

CRITERION: AC-02 The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
VERDICT: met
EVIDENCE: The exact commit's GitHub Actions run 45846041860 passed the composite, compared its outputs against the local command, and ran tests/setup.sh on the hosted runner. Its logs show Python 3.14.10, ansible-core 2.22.0 and ansible-lint 26.11.1, plus refusal of both a wrong Python checksum and corrupt wheel hashes. Locally, tests/check.sh and tests/scope.sh passed the path, profile, inventory, archive and environment assertions, including the synthetic credential sentinel check.

CRITERION: AC-03 The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
VERDICT: not met
EVIDENCE: At the reviewed commit, tests/hook.sh and tests/scope.sh passed the partial-stage, unrelated-file, shared-config, imported-task and index assertions. In a separate fixture, I staged only a value change to a tracked JSON file listed in the playbook's vars_files. The hook and direct staged mode exited 0 without invoking lint. The ordinary direct command linted the affected playbook and reported a production-profile pass. The fixture's Git index tree stayed identical across the checks.

CRITERION: AC-04 The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
VERDICT: met
EVIDENCE: Local actionlint 1.7.12 and tests/release.sh passed on the exact export. GitHub run 45846041860 completed successfully at e661aefe97563d77e84fba53d02b09d0fd378937, with both fixtures and workflows jobs passing. The pinned release workflow calls GitVersion only after the fixture and ref gates, and recovery uses the shared GitHub Release action at a stable tag verified against the tested commit. This review exercised release eligibility on synthetic refs without publishing.

FINDING: F-01
KIND: factual
SEVERITY: blocking
WHERE: scripts/check.py:81-99, README.md:3-5, AC-01
EVIDENCE: Role discovery requires tasks/main.yml or tasks/main.yaml. A handler-only role is a supported Ansible role layout and passed the pinned native linter, but the wrapper refused it as an empty scope. https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_reuse_roles.html#role-directory-structure
PROPOSAL: Discover roles from Ansible's supported role layout, including roles without a default task entry point. Add a synthetic role-only regression through the public check command.

FINDING: F-02
KIND: factual
SEVERITY: blocking
WHERE: examples/native-hook/.githooks/pre-commit:17-28, scripts/check.py:159-177, AC-03
EVIDENCE: Both staged entry points skipped a tracked JSON dependency referenced by a playbook's literal vars_files entry. Staged filtering dropped the file before the reference resolver could select its playbook.
PROPOSAL: Consider staged changes to literal dependencies before filtering by suffix. Keep the skip for unrelated staged paths and prove both outcomes through the sample hook.

FINDING: F-03
KIND: factual
SEVERITY: should-fix
WHERE: scripts/.tool-versions, scripts/python-archive.tsv, scripts/setup.sh:37-57, scripts/requirements.txt:1-2, tests/setup.sh:5-6, renovate.json, Design tool pins, conventions/delivery.md#pinning-and-updates
EVIDENCE: Renovate's asdf manager can find the Python version in .tool-versions, but no configured update mechanism pairs a change there with the standalone archive build and verified digest. The setup test hardcodes the old Python patch, and the lock generation command independently carries it. The next version-only update cannot install and pass setup as proposed. https://docs.renovatebot.com/modules/manager/asdf/
PROPOSAL: Make the executable archive pin's full update discoverable and keep the runtime version, build and verified digest together. Derive the setup test expectation from the expected runtime pin and prove that the updater can prepare a usable version change.

FINDING: F-04
KIND: factual
SEVERITY: should-fix
WHERE: GitHub repository settings, conventions/delivery.md#git-and-versioning
EVIDENCE: The repository API reports delete_branch_on_merge false. The delivery convention requires it enabled.
PROPOSAL: Enable automatic merged-branch deletion for this repository.

FINDING: F-05
KIND: factual
SEVERITY: should-fix
WHERE: GitHub repository settings, .github/workflows/, conventions/repository-security.md#public-repositories
EVIDENCE: GitHub reports secret scanning and push protection disabled and private vulnerability reporting false for this public repository. Default CodeQL is not configured, and the proposed tree has no calls to the required shared CodeQL and Scorecard workflows.
PROPOSAL: Enable the public-repository security settings and add the pinned shared CodeQL and Scorecard callers for the supported languages and repository type.

### R-10

CRITERION: AC-01 Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
VERDICT: not met
EVIDENCE: At 8a60b5e3f9448b34dddac071bf2e7ff4b5c2b0dd, local tests/check.sh and tests/scope.sh passed, including the revised handler-only fixture. In a separate scoped role with only tasks/configure.yml, pinned ansible-lint passed the production profile and pinned ansible-playbook --syntax-check accepted an import_role with tasks_from: configure. The check script exited 1 with "No Ansible content in working-directory" when asked to check that standalone role.

CRITERION: AC-02 The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
VERDICT: met
EVIDENCE: GitHub Actions Test run 45857577938 completed successfully at 8a60b5e3f9448b34dddac071bf2e7ff4b5c2b0dd. The composite accepted the clean fixture, and the comparison step confirmed the failing composite outcome and the same Python 3.14.10, ansible-core 2.22.0 and ansible-lint 26.11.1 versions as the direct check. The hosted setup fixture reported the archive-checksum and wheel-hash refusals. Local tests/check.sh and tests/scope.sh passed the invalid profile, escaping path, dynamic inventory, locked archive and isolated process assertions.

CRITERION: AC-03 The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
VERDICT: not met
EVIDENCE: At the reviewed commit, local tests/hook.sh and tests/scope.sh passed, including the JSON reference, partial-stage, unrelated-file, and index assertions. In an independent repository with a valid playbook and a pre-existing unfinished YAML example under docs, I staged only README.md. The new hook exited 1 with a YAML parser diagnostic for the unchanged example. The previous hook skipped the same staged edit and exited 0.

CRITERION: AC-04 The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
VERDICT: met
EVIDENCE: Local actionlint 1.7.12 and tests/release.sh passed on the exact export. The fixtures and workflows jobs passed in hosted run 45857577938 at the same commit. The release workflow requires the read-only fixture workflow before the ref gate and the pinned shared GitVersion release call. The recovery path calls the pinned shared Release action after validating the tested exact stable tag. I verified eligibility on synthetic refs without publishing.

FINDING: F-01
KIND: factual
SEVERITY: blocking
WHERE: scripts/check.py:21-22, scripts/check.py:83-101, AC-01
EVIDENCE: After adding standard main entry points for roles, discovery still ignores standard role content with an alternate task entry point. A scoped role with only tasks/configure.yml passed the production linter, and an import_role using tasks_from: configure passed native syntax checking. The wrapper rejected the role as empty.
PROPOSAL: Recognize roles with standard role directories and alternate entry points. Add a fixture with an alternate task entry point that passes both selection and native verification.

FINDING: F-02
KIND: factual
SEVERITY: blocking
WHERE: examples/native-hook/.githooks/pre-commit:7-9, scripts/check.py:83-95, scripts/check.py:182-190, AC-03
EVIDENCE: The change that permits staged JSON references now sends every nonempty stage to a scope-wide YAML parse. An unchanged, unrelated unfinished YAML example under docs prevented a commit with only README.md staged. The parse runs before the code decides whether the staged file affects any playbook.
PROPOSAL: Check staged relevance before rejecting parse failures in unrelated files. Keep refusal of malformed selected Ansible content and add a regression that covers unrelated staging with a pre-existing incomplete YAML sample.

FINDING: F-03
KIND: factual
SEVERITY: should-fix
WHERE: scripts/.tool-versions, scripts/python-archive.tsv, scripts/setup.sh:37-57, scripts/requirements.txt:1-2, renovate.json, Design tool pins, conventions/delivery.md#pinning-and-updates
EVIDENCE: The setup fixture now derives its expected version from .tool-versions. Renovate can discover that Python version, while the required build date and independently pinned SHA-256 remain outside its configured update path. The lock generation command also carries the Python version. A standalone update to the asdf pin still leaves the installer pointed at the previous build and checksum. https://docs.renovatebot.com/modules/manager/asdf/
PROPOSAL: Make the executable archive's version, build and verified digest part of one reviewable update. Verify the updater can prepare the corresponding hash-locked dependency update against that runtime.

### R-11

CRITERION: AC-01 Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
VERDICT: met
EVIDENCE: At a7e80a8073b3692fe2ff09ff86814d268dd8d4d8, local tests/check.sh and tests/scope.sh passed the clean, strict-warning, lint-only, syntax, suppression and empty-scope assertions. The role fixtures included handler-only and alternate task entry points. A separate scoped role with only tasks/configure.yml passed the wrapper and native syntax checking of a play that imported it with tasks_from: configure.

CRITERION: AC-02 The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
VERDICT: met
EVIDENCE: GitHub Test run 45858870721 completed successfully at the reviewed commit. The composite and direct check agreed on the expected refusal and reported Python 3.14.10, ansible-core 2.22.0 and ansible-lint 26.11.1. The hosted setup test logged refusals for the wrong archive checksum and corrupt wheel hashes. Local tests/check.sh and tests/scope.sh passed the invalid profile, escaping path, dynamic inventory, locked dependency and isolated environment assertions.

CRITERION: AC-03 The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
VERDICT: not met
EVIDENCE: Local tests/hook.sh and tests/scope.sh passed, and the independent README-only stage with an unfinished YAML example under docs now exited 0 with no lint output and an unchanged index. In a second repository containing a role with tasks/main.yml and an unchanged draft.yml under its tasks directory, the same README-only stage exited 1 with a YAML parser diagnostic for the unstaged draft. The index also stayed unchanged in this reproduction.

CRITERION: AC-04 The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
VERDICT: met
EVIDENCE: Local actionlint 1.7.12 and tests/release.sh passed on the exact export. Hosted run 45858870721 finished with both fixtures and workflows jobs passing at a7e80a8073b3692fe2ff09ff86814d268dd8d4d8. The release workflow requires the fixture and ref gates before calling the pinned shared GitVersion workflow. The recovery path verifies the tested tag before invoking the pinned shared release action. The release test exercised synthetic refs without publication.

FINDING: F-01
KIND: factual
SEVERITY: blocking
WHERE: scripts/check.py:147-167, scripts/check.py:192-200, AC-03
EVIDENCE: The change suppresses unrelated parse failures during initial YAML discovery. Reference discovery still parses every YAML file in each discovered role before it decides staged relevance. A README-only stage was refused due to an unchanged malformed file in a role's tasks directory.
PROPOSAL: Defer malformed role-file errors until the staged selection includes that role or the affected reference. Prove the hook skips unrelated staging and still rejects malformed staged role content.

FINDING: F-02
KIND: factual
SEVERITY: should-fix
WHERE: README.md:63-68, scripts/.tool-versions, scripts/python-archive.tsv, scripts/setup.sh:37-57, scripts/requirements.txt:1-2, renovate.json, Design tool pins, conventions/delivery.md#pinning-and-updates
EVIDENCE: The README now documents the deliberate manual update of the upstream standalone build and independently verified archive digest. Renovate can propose the .tool-versions change, and its configured managers do not discover the coupled archive build and SHA-256. A version-only proposal remains incomplete, and archive-build changes for the same Python version remain manual. https://docs.renovatebot.com/modules/manager/asdf/
PROPOSAL: Make the underlying archive dependency discoverable and coordinate its version, build, verified digest, and generated lock in a single reviewable update.

### R-12

CRITERION: AC-01 Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
VERDICT: met
EVIDENCE: At cdafd6932e926c606ef829dc7888b10a4d472487, local tests/check.sh and tests/scope.sh exited 0 with the pinned toolchain. They checked clean playbooks and handler-only and alternate-entry roles, and asserted refusals for strict warnings, production-rule violations, missing modules, suppressed checks and empty scopes.

CRITERION: AC-02 The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
VERDICT: met
EVIDENCE: GitHub Actions Test run 45859953475 finished successfully at cdafd6932e926c606ef829dc7888b10a4d472487. The fixture logs show the composite failing as expected on the negative fixture and matching the direct check's Python 3.14.10, ansible-core 2.22.0 and ansible-lint 26.11.1 outputs. The hosted setup fixture ran a fresh installation and reported refusals for the wrong archive checksum and corrupt package hashes. Local tests/check.sh and tests/scope.sh passed the invalid profile, escaping path, dynamic inventory, locked dependency and isolated process assertions.

CRITERION: AC-03 The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
VERDICT: met
EVIDENCE: Local tests/hook.sh and tests/scope.sh passed at the reviewed commit. I separately reran unrelated-role-draft, referenced-vars and imported-task. The README-only stage passed despite the unchanged malformed role task file and preserved the index. Staging an edit to that role made the hook report load-failure[yaml]. The staged JSON variable file and imported task selected their Ansible checks, and the fixtures verified index preservation. The partial-stage cases established that hook verdicts follow the staged rather than the working copy.

CRITERION: AC-04 The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
VERDICT: met
EVIDENCE: Local actionlint 1.7.12 and tests/release.sh exited 0 at the exact export. Both fixtures and workflows finished successfully in hosted run 45859953475. The read-only fixture workflow gates the ref check and the pinned shared GitVersion release workflow. Recovery calls the pinned shared release action after verifying the tested stable tag. The ref tests used synthetic commits and tags without publication.

FINDING: F-01
KIND: factual
SEVERITY: should-fix
WHERE: README.md:63-68, scripts/.tool-versions, scripts/python-archive.tsv, scripts/setup.sh:37-57, scripts/requirements.txt:1-2, renovate.json, Design tool pins, conventions/delivery.md#pinning-and-updates
EVIDENCE: The README documents the manual update of the upstream standalone build and independently pinned archive digest. Renovate can discover the Python version in .tool-versions. The configured managers do not discover the coupled archive build and SHA-256, so a Python version-only proposal remains incomplete and same-version archive rebuilds still need manual discovery. https://docs.renovatebot.com/modules/manager/asdf/
PROPOSAL: Make the archive dependency discoverable to the updater and coordinate the version, build, verified digest and generated dependency lock in one reviewed change.

### R-13

CRITERION: AC-01 Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
VERDICT: met
EVIDENCE: Local tests/check.sh and tests/scope.sh exited 0 on the export of 4d5b84fd2ced82e9870591cb93fbed2e75bef23c. They exercised clean playbooks, handler-only and alternate-entry roles, and refusal for production-rule violations, strict warnings, invalid syntax, suppression and empty scopes. The same tests passed on the hosted runner.

CRITERION: AC-02 The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
VERDICT: met
EVIDENCE: In exact Test run 45871394397, the fixture logs show the intended composite failure and match all three direct-check outputs: Python 3.14.10, ansible-core 2.22.0 and ansible-lint 26.11.1. The hosted setup test completed a fresh installation and confirmed refusal for the wrong archive checksum and corrupt package hashes. Local tests/check.sh and tests/scope.sh passed invalid-input, locked archive and controlled-environment assertions.

CRITERION: AC-03 The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
VERDICT: met
EVIDENCE: Local tests/hook.sh and tests/scope.sh passed on the exact export. The tests confirmed partial staging, skipping unrelated changes in the presence of malformed drafts, following staged JSON variables and imported tasks, retaining strict validation when a role is affected, and preserving source and index.

CRITERION: AC-04 The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
VERDICT: met
EVIDENCE: In exact Test run 45871394397, the read-only fixture and workflow jobs passed, including pinned actionlint, pinned ShellCheck and the synthetic release gate. Local actionlint 1.7.12 and tests/release.sh also passed. The caller requires the read-only fixtures before the ref gate and pins the shared GitVersion release workflow and exact-tag recovery action. The release guard was tested with synthetic refs without publication.

FINDING: F-01
KIND: factual
SEVERITY: should-fix
WHERE: .github/workflows/codeql.yml:19-35, pinned vhco-pro/.github reusable-codeql-actions.yml and reusable-codeql-js.yml, conventions/github-actions.md#security
EVIDENCE: Both pinned reusable CodeQL jobs leave the default checkout credential persistence enabled. Neither scan job pushes. The pinned standard requires persist-credentials false for these checkouts. https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/action.yml
PROPOSAL: Disable persistence in both shared CodeQL checkout steps and adopt the corrected shared workflow pin.

FINDING: F-02
KIND: factual
SEVERITY: should-fix
WHERE: .github/workflows/codeql.yml and scorecard.yml, pinned vhco-pro/.github reusable-codeql-actions.yml, reusable-codeql-js.yml and reusable-scorecard.yml, conventions/github-actions.md#execution and #security
EVIDENCE: All three called workflows omit workflow-level permissions: {}. The Python wrapper and Scorecard jobs omit a job timeout. Both CodeQL workflows omit defaults.run.shell. The caller's workflow settings do not define those values inside the reusable workflows.
PROPOSAL: Apply the shared workflow permission and timeout defaults and add the standard shell defaults to both CodeQL workflows. Keep the Scorecard publishing workflow's default-shell exception because its provider checks for workflow-level defaults.

FINDING: F-03
KIND: factual
SEVERITY: should-fix
WHERE: .github/workflows/scorecard.yml:2-26, README.md Security checks
EVIDENCE: The Scorecard job checks public visibility only. Its workflow_dispatch trigger can select another branch, and OpenSSF's results verifier requires the tested ref to be the analyzed repository's default branch. The production source supports validation through the pinned reusable workflow. No Scorecard execution was observed for this feature commit. https://github.com/ossf/scorecard-infra/blob/4612b925b7c44e3762267c3bc5b1a8ebaba16740/api/app/server/post_results.go
PROPOSAL: Gate Scorecard publication on the public default branch for every trigger. Verify the first eligible hosted run and published analysis on that branch when authorized.

FINDING: F-04
KIND: factual
SEVERITY: nit
WHERE: .github/workflows/codeql.yml:25-35, pinned vhco-pro/.github reusable-codeql-js.yml
EVIDENCE: Exact CodeQL run 45871394766 scanned 2 of 2 Python files and 5 of 5 Actions files. The Python scan job displays JS/TS in its name, and GitHub recorded its result under /language:js-ts. The current Actions result uses its own distinct category.
PROPOSAL: Use the selected language in the job display name and CodeQL result category while preserving the JavaScript and TypeScript default for existing callers.

FINDING: F-05
KIND: factual
SEVERITY: should-fix
WHERE: README.md:63-68, scripts/.tool-versions, scripts/python-archive.tsv, scripts/setup.sh:37-57, scripts/requirements.txt:1-2, renovate.json, Design tool pins, conventions/delivery.md#pinning-and-updates
EVIDENCE: Renovate can discover the Python version in .tool-versions. The configured managers do not discover the coupled archive build and SHA-256. The README documents the deliberate manual update, including the linked Python version and generated wheel lock. https://docs.renovatebot.com/modules/manager/asdf/
PROPOSAL: Make the archive dependency discoverable to the updater and coordinate its version, build, verified digest and generated dependency lock in one reviewed change.

### R-14

CRITERION: AC-01 Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
VERDICT: met
EVIDENCE: Local tests/check.sh and tests/scope.sh passed on the export of 2b8efa933b9f4e55591a626c4c159ad2e8349e71. They exercised clean playbooks, handler-only roles and alternate task entry points, plus refusal for production-rule violations, strict warnings, invalid syntax, suppression and empty scopes. Hosted Test run 45872115680 passed those tests on the same commit.

CRITERION: AC-02 The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
VERDICT: met
EVIDENCE: Exact Test run 45872115680 confirmed the expected negative composite outcome and matching direct-check outputs for Python 3.14.10, ansible-core 2.22.0 and ansible-lint 26.11.1. The hosted setup fixture completed a fresh installation and reported both the wrong archive checksum and wrong wheel hash refusals. Local tests/check.sh and tests/scope.sh passed the input, locked archive and isolated environment assertions.

CRITERION: AC-03 The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
VERDICT: met
EVIDENCE: Local tests/hook.sh and tests/scope.sh passed on the exact commit. They checked partial staging, unrelated changes beside malformed YAML, staged JSON and imported task references, refusal for malformed affected roles, and source and index preservation.

CRITERION: AC-04 The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
VERDICT: met
EVIDENCE: Exact Test run 45872115680 passed both fixture and workflow jobs, including pinned actionlint, ShellCheck, and release-gate tests on synthetic refs. Local actionlint 1.7.12 and tests/release.sh passed. The ref gate still follows successful read-only fixtures and precedes the shared GitVersion workflow and recovery action. Exact CodeQL run 45872116227 scanned 5 of 5 Actions files and 2 of 2 Python files. I evaluated the exact Scorecard guard with synthetic event inputs using GitHub's documented comparisons. It admitted a public default branch and refused a differently named branch, a same-name tag, a private branch and an absent ref type. A case-only branch name passes the GitHub comparison, and OpenSSF separately checks exact default-branch identity before publication. Scorecard publication was not observed on this feature commit.

FINDING: F-01
KIND: factual
SEVERITY: should-fix
WHERE: .github/workflows/codeql.yml and scorecard.yml, external vhco-pro/.github reusable-codeql-actions.yml, reusable-codeql-js.yml and reusable-scorecard.yml at e03ad61274b2bf0738b36ed67dff1c376321fb64, conventions/github-actions.md#security and #execution
EVIDENCE: The unchanged shared CodeQL workflows leave checkout credential persistence enabled and omit shell defaults. The three pinned shared workflows omit top-level permissions: {}. The Python and Scorecard jobs omit explicit timeouts. These are inherited from the external pins. The public fixture uses disabled checkout persistence and explicitly scoped permissions and timeouts.
PROPOSAL: Correct the shared workflows before adopting their updated pins. Preserve the Scorecard provider restriction on top-level defaults in its publishing workflow.

FINDING: F-02
KIND: factual
SEVERITY: nit
WHERE: .github/workflows/codeql.yml Python job, external vhco-pro/.github reusable-codeql-js.yml at e03ad61274b2bf0738b36ed67dff1c376321fb64
EVIDENCE: CodeQL logs at the exact commit confirm Python coverage. The external wrapper still labels the job JS/TS and uploads the Python analysis under /language:js-ts. The Actions analysis uses its own category.
PROPOSAL: Derive the shared wrapper's display name and category from the language input when that dependency is revised.

FINDING: F-03
KIND: factual
SEVERITY: should-fix
WHERE: README.md:63-68, scripts/.tool-versions, scripts/python-archive.tsv, scripts/setup.sh:37-57, scripts/requirements.txt:1-2, renovate.json, Design tool pins, conventions/delivery.md#pinning-and-updates
EVIDENCE: The documented manual update procedure pairs the Python version with the verified standalone archive build and digest and refreshed wheel lock. Renovate sees the Python version in .tool-versions, and its configured managers do not discover or coordinate the build and digest. https://docs.renovatebot.com/modules/manager/asdf/
PROPOSAL: Make the archive dependency discoverable to the updater and coordinate the version, build, verified digest and generated lock in one reviewed change.

### R-15

CRITERION: AC-01 Clean Ansible content passes the production profile and syntax checks. Production-rule violations, syntax failures, suppressed checks on selected content and empty scopes fail.
VERDICT: met
EVIDENCE: Local tests/check.sh and tests/scope.sh passed on the export of 78bf1dcaa075590a7e5ca8f98ebd7bf26bb1ec9e. They exercised clean playbooks, handler-only roles and alternate task entry points, plus refusal for production-rule violations, strict warnings, invalid syntax, suppression and empty scopes. The exact hosted Test run 45877866273 passed these fixtures.

CRITERION: AC-02 The action uses its exact dependency pins, reports installed versions and rejects an invalid profile, an escaping path, dynamic inventory or failed setup. Syntax checking uses isolated synthetic inventory without ambient configuration or credentials.
VERDICT: met
EVIDENCE: Exact Test run 45877866273 confirmed the expected negative composite outcome and matching direct-check outputs for Python 3.14.10, ansible-core 2.22.0 and ansible-lint 26.11.1. The hosted setup fixture completed a fresh installation and reported both the wrong archive checksum and wrong wheel hash refusals. Local tests/check.sh and tests/scope.sh passed the input refusals, locked archives and isolated environment checks.

CRITERION: AC-03 The direct command and native hook share validation behavior. Hook checks skip unrelated staged files, select affected Ansible content and use the index snapshot. The source and index stay intact.
VERDICT: met
EVIDENCE: Local tests/hook.sh and tests/scope.sh passed on the exact commit. They checked partial staging, unrelated changes beside malformed YAML, staged JSON and imported task references, refusal for malformed affected roles, and source and index preservation. The hosted native fixture step passed at the same commit.

CRITERION: AC-04 The repository contains synthetic read-only public fixtures, lintable workflows and shared GitVersion release wiring that requires passing fixture tests before tagging.
VERDICT: met
EVIDENCE: Exact Test run 45877866273 passed both jobs, including pinned actionlint, ShellCheck, and release-gate tests on synthetic refs. Local actionlint 1.7.12 and tests/release.sh passed. The read-only fixture gates the release ref check and the pinned GitVersion or recovery workflow path. GitHub's public stable v1.2.5 release tag resolves to 119c3c5c884b2b9a6529e741b239eac288942262, the SHA pinned by both CodeQL callers. Exact CodeQL run 45877866535 showed persist-credentials: false in both checkout logs, scanned 5 of 5 Actions files and 2 of 2 Python files, and stored both analyses. No Scorecard publication or release was exercised in this feature-branch review.

FINDING: F-01
KIND: factual
SEVERITY: should-fix
WHERE: .github/workflows/scorecard.yml, external vhco-pro/.github reusable-scorecard.yml at e03ad61274b2bf0738b36ed67dff1c376321fb64, conventions/github-actions.md#security and #execution
EVIDENCE: The unchanged shared Scorecard workflow omits top-level permissions: {} and the analysis job omits an explicit timeout. The shared CodeQL v1.2.5 workflow pin now supplies the permission and timeout settings and disables checkout credential persistence for both scans.
PROPOSAL: Apply the empty top-level permission set and an explicit timeout in the shared Scorecard workflow, then verify and adopt that released pin. Preserve the provider's restriction on top-level defaults.

FINDING: F-02
KIND: factual
SEVERITY: nit
WHERE: .github/workflows/codeql.yml Python job, external vhco-pro/.github reusable-codeql-js.yml at 119c3c5c884b2b9a6529e741b239eac288942262
EVIDENCE: Exact hosted logs confirm Python coverage. The external wrapper still labels the job JS/TS and uploads the Python analysis under /language:js-ts. The Actions analysis uses its own category.
PROPOSAL: Derive the shared wrapper's display name and analysis category from the language input when that dependency is revised.

FINDING: F-03
KIND: factual
SEVERITY: should-fix
WHERE: README.md:63-68, scripts/.tool-versions, scripts/python-archive.tsv, scripts/setup.sh:37-57, scripts/requirements.txt:1-2, renovate.json, Design tool pins, conventions/delivery.md#pinning-and-updates
EVIDENCE: The unchanged manual procedure pairs the Python version with the verified standalone archive build and digest and refreshed wheel lock. Renovate sees the Python version in .tool-versions, and its configured managers do not discover or coordinate the build and digest. https://docs.renovatebot.com/modules/manager/asdf/
PROPOSAL: Make the archive dependency discoverable to the updater and coordinate the version, build, verified digest and generated lock in one reviewed change.

## Sources

- [Ansible-lint production profile](https://docs.ansible.com/projects/lint/profiles/) and [syntax-check rules](https://docs.ansible.com/projects/lint/rules/syntax-check/) describe the default gate.
- [AI Forge write-content](https://github.com/ansible-community/ai-forge/blob/28a9a580b19e208e4c1bbd6146aa60e8aafe8a9f/ansible-content-development/module/skills/write-content/SKILL.md) describes authoring content. [AI Forge write-content-tests](https://github.com/ansible-community/ai-forge/blob/28a9a580b19e208e4c1bbd6146aa60e8aafe8a9f/ansible-content-development/module/skills/write-content-tests/SKILL.md) and [Molecule role testing](https://docs.ansible.com/projects/molecule/getting-started-roles/) describe functional fixtures. [Ansible DevTools](https://ansible.github.io/vscode-ansible/ai/skills/) lists upstream authoring skills.
- [PowerShell fixture workflow](https://github.com/vhco-pro/pwsh-ci-action/blob/v0.1.1/.github/workflows/test.yml) demonstrates checking direct and composite verdicts. [GitHub release workflow](https://github.com/vhco-pro/gh-release-workflow/blob/b18de6d2f305f971afe01ba31e17bde5966b1567/.github/workflows/gh-release.yml) owns GitVersion tagging and publication.
