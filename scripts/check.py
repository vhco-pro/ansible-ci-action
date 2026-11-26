"""Run Ansible lint against a staged or working snapshot of one checkout."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

import yaml

PROFILES = {"min", "basic", "moderate", "safety", "shared", "production"}
CONFIG_NAMES = (".ansible-lint", ".ansible-lint.yml", ".ansible-lint.yaml", ".config/ansible-lint.yml", ".config/ansible-lint.yaml")
IGNORE_NAMES = (".ansible-lint-ignore", ".config/ansible-lint-ignore.txt")
SAFE_CONFIG = {"profile", "verbosity", "var_naming_pattern", "loop_var_prefix", "enable_list", "only_builtins_allow_collections"}
YAML_SUFFIXES = {".yml", ".yaml"}
TOOL_BIN = Path(sys.executable).parent


def git(workspace, *args):
    return subprocess.check_output(["git", "-C", str(workspace), *args])


def contained_path(root, value, label):
    path = Path(value)
    if path.is_absolute():
        raise ValueError(f"{label} must be checkout-relative.")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"{label} escapes the checkout.")
    return resolved


def git_paths(workspace, *args):
    return [Path(os.fsdecode(value)) for value in git(workspace, *args).split(b"\0") if value]


def snapshot(workspace, tree, staged):
    if staged:
        git(workspace, "checkout-index", "--all", f"--prefix={tree}/")
    else:
        for relative in git_paths(workspace, "ls-files", "--cached", "--deduplicate", "-z"):
            source = contained_path(workspace, relative, "Tracked path")
            if not source.is_file():
                raise ValueError(f"Tracked path is missing or not a regular file: {relative}")
            destination = tree / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    for path in tree.rglob("*"):
        if path.is_symlink() and not path.resolve().is_relative_to(tree):
            raise ValueError(f"Tracked symlink escapes the checkout: {path.relative_to(tree)}")


def lint_targets(scope):
    roles = set()
    playbooks = []
    for path in sorted(scope.rglob("*")):
        if not path.is_file() or path.suffix not in YAML_SUFFIXES:
            continue
        if path.stem == "main" and path.parent.name == "tasks":
            roles.add(path.parent.parent)
        if path.name.startswith(".") or any(part.startswith(".") for part in path.relative_to(scope).parts[:-1]):
            continue
        node = yaml.compose(path.read_text())
        if not isinstance(node, yaml.SequenceNode):
            continue
        for entry in node.value:
            if isinstance(entry, yaml.MappingNode) and any(key.value in {"hosts", "import_playbook"} for key, _ in entry.value):
                playbooks.append(path)
                break
    return sorted(roles) + [playbook for playbook in playbooks if not any(playbook.is_relative_to(role) for role in roles)]


def changed_scopes(workspace, scope):
    paths = git_paths(workspace, "diff", "--cached", "--no-renames", "--name-only", "-z")
    changed = []
    for path in paths:
        if path == Path("ci/ansible-content.lock") or (path.parts and path.parts[0] == "ci"):
            return None
        if path.as_posix().endswith(CONFIG_NAMES + IGNORE_NAMES) or path.name == "ansible.cfg":
            return None
        if path.is_relative_to(scope) and (path.suffix in YAML_SUFFIXES or any(part in {"roles", "templates", "files"} for part in path.parts)):
            if not any(part.startswith(".") for part in path.parts):
                changed.append(path.relative_to(scope))
    return changed


def select_targets(scope, staged_changes):
    targets = lint_targets(scope)
    if staged_changes is None:
        return targets
    if all(scope / path in targets and (scope / path).is_file() for path in staged_changes):
        return [target for target in targets if target.relative_to(scope) in staged_changes]
    # A dependency, deletion or role change can affect more than one play.
    return targets


def lint_config(tree, scope, scratch):
    locations = (scope, *[parent for parent in scope.parents if parent.is_relative_to(tree)])
    for location in locations:
        for name in IGNORE_NAMES:
            ignored = location / name
            if ignored.is_file() and any(line.strip() and not line.lstrip().startswith("#") for line in ignored.read_text().splitlines()):
                raise ValueError(f"Lint ignore entries are unsupported: {ignored.relative_to(tree)}")
        for name in CONFIG_NAMES:
            config = location / name
            if not config.is_file():
                continue
            values = yaml.safe_load(config.read_text())
            if values is None:
                return config
            if not isinstance(values, dict):
                raise ValueError("Ansible lint configuration must be a mapping.")
            forbidden = sorted(str(key) for key, value in values.items() if key not in SAFE_CONFIG and value not in (None, [], {}))
            if forbidden:
                raise ValueError(f"Unsupported lint config entries: {', '.join(forbidden)}")
            return config
    config = scratch / "lint.yml"
    config.write_text("{}\n")
    return config


def fixture_inventory(tree, value, scratch):
    if not value:
        inventory = scratch / "inventory.yml"
        inventory.write_text("all:\n  hosts:\n    localhost:\n      ansible_connection: local\n")
        return inventory
    inventory = contained_path(tree, value, "fixture-inventory")
    if not inventory.is_file() or inventory.suffix not in YAML_SUFFIXES | {".ini"}:
        raise ValueError("fixture-inventory must name a static YAML or INI inventory file.")
    text = inventory.read_text()
    if inventory.suffix in YAML_SUFFIXES:
        document = yaml.safe_load(text)
        if not isinstance(document, dict) or "plugin" in document:
            raise ValueError("fixture-inventory must name a static YAML or INI inventory file.")
    elif text.lstrip().startswith("#!"):
        raise ValueError("fixture-inventory must name a static YAML or INI inventory file.")
    return inventory


def isolated_environment(scratch, inventory, scope):
    home = scratch / "home"
    temporary = scratch / "tmp"
    home.mkdir()
    temporary.mkdir()
    config = scratch / "ansible.cfg"
    config.write_text("[defaults]\n[inventory]\nenable_plugins = yaml, ini\n")
    return {
        "PATH": f"{TOOL_BIN}:/usr/bin:/bin",
        "HOME": str(home),
        "TMPDIR": str(temporary),
        "LC_ALL": "C.UTF-8",
        "ANSIBLE_CONFIG": str(config),
        "ANSIBLE_HOME": str(scratch / "ansible-home"),
        "ANSIBLE_INVENTORY": str(inventory),
        "ANSIBLE_INVENTORY_ENABLED": "yaml,ini",
        "ANSIBLE_INVENTORY_ANY_UNPARSED_IS_FAILED": "true",
        "ANSIBLE_INVENTORY_UNPARSED_IS_FAILED": "true",
        "ANSIBLE_ROLES_PATH": f"{scratch / 'roles'}:{scope / 'roles'}",
        "ANSIBLE_COLLECTIONS_PATH": str(scratch / "collections"),
        "ANSIBLE_COLLECTIONS_SCAN_SYS_PATH": "false",
    }


def locked_archive(tree, dependency):
    if not isinstance(dependency, dict) or set(dependency) != {"kind", "archive", "version", "sha256"}:
        raise ValueError("Each content lock entry needs kind, archive, version and sha256.")
    if dependency["kind"] not in {"role", "collection"} or not isinstance(dependency["version"], str) or not dependency["version"]:
        raise ValueError("Content requires a role or collection kind and an exact version.")
    archive = contained_path(tree, dependency["archive"], "Content archive")
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != dependency["sha256"]:
            raise ValueError(f"Content archive checksum mismatch: {archive.relative_to(tree)}")
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsafe path in content archive: {archive.relative_to(tree)}")
        if dependency["kind"] == "collection":
            manifest = bundle.extractfile("MANIFEST.json")
            if manifest is None or json.load(manifest)["collection_info"]["version"] != dependency["version"]:
                raise ValueError(f"Collection manifest version mismatch: {archive.relative_to(tree)}")
    return archive


def install_content(tree, scratch, env):
    lock = tree / "ci/ansible-content.lock"
    if not lock.is_file():
        return
    manifest = yaml.safe_load(lock.read_text())
    if not isinstance(manifest, dict) or set(manifest) != {"dependencies"} or not isinstance(manifest["dependencies"], list):
        raise ValueError("The Ansible content lock needs a dependencies list.")
    for dependency in manifest["dependencies"]:
        archive = locked_archive(tree, dependency)
        kind = dependency["kind"]
        destination = scratch / ("collections" if kind == "collection" else "roles")
        subprocess.run(
            [str(TOOL_BIN / "ansible-galaxy"), kind, "install", "--no-deps", "-p", str(destination), str(archive)],
            cwd=scratch, env=env, check=True,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    workspace = Path(os.environ.get("ANSIBLE_CI_WORKSPACE") or os.environ.get("GITHUB_WORKSPACE") or ".").resolve()
    if Path(os.fsdecode(git(workspace, "rev-parse", "--show-toplevel")).rstrip("\n")) != workspace:
        raise ValueError("Use the checkout root as workspace.")
    scope = contained_path(workspace, os.environ.get("ANSIBLE_CI_WORKING_DIRECTORY") or ".", "working-directory").relative_to(workspace)
    profile = os.environ.get("ANSIBLE_CI_PROFILE") or "production"
    if profile not in PROFILES:
        raise ValueError(f"Unknown Ansible lint profile: {profile}")
    changes = changed_scopes(workspace, scope) if args.staged else None
    if changes == []:
        return 0
    with tempfile.TemporaryDirectory() as temporary:
        scratch = Path(temporary)
        tree = scratch / "tree"
        tree.mkdir()
        snapshot(workspace, tree, args.staged)
        root = tree / scope
        targets = select_targets(root, changes)
        if not targets:
            if args.staged:
                return 0
            raise ValueError("No Ansible content in working-directory.")
        config = lint_config(tree, root, scratch)
        inventory = fixture_inventory(tree, os.environ.get("ANSIBLE_CI_FIXTURE_INVENTORY"), scratch)
        env = isolated_environment(scratch, inventory, root)
        install_content(tree, scratch, env)
        return subprocess.run(
            [str(TOOL_BIN / "ansible-lint"), "--offline", "--strict", "--profile", profile,
             "--project-dir", str(root), "-c", str(config), *map(str, targets)],
            cwd=root, env=env, check=False,
        ).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, yaml.YAMLError, tarfile.TarError, KeyError, subprocess.CalledProcessError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
