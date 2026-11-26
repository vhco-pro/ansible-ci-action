"""Run Ansible lint against a staged or working snapshot of one checkout."""
import argparse
import hashlib
import json
import os
import re
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
CONTENT_LOCK = Path("ci/ansible-content.lock")
TASK_KEYS = {
    "action", "local_action", "block", "rescue", "always", "register", "notify",
    "include_tasks", "import_tasks", "include_role", "import_role", "include_vars",
}
FILE_DIRECTIVES = {"import_tasks", "include_tasks", "import_playbook", "include_vars", "vars_files"}
PLAY_HEADERS = {"hosts", "import_playbook"}
PLAY_BODY = {"tasks", "pre_tasks", "post_tasks", "handlers", "roles", "gather_facts"}
DEPENDENCY_DIRS = {"roles", "tasks", "handlers", "defaults", "vars", "templates", "files", "meta", "group_vars", "host_vars"}
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


def yaml_shape(text):
    documents = list(yaml.compose_all(text))
    keys = {
        key.value for document in documents if isinstance(document, yaml.SequenceNode)
        for entry in document.value if isinstance(entry, yaml.MappingNode)
        for key, _ in entry.value if isinstance(key, yaml.ScalarNode)
    }
    return keys, len(documents) > 1


def looks_like_tasks(keys):
    return bool(keys & (PLAY_HEADERS | PLAY_BODY | TASK_KEYS)) or any(key.count(".") >= 2 for key in keys)


def lint_targets(scope):
    roles = set()
    playbooks = []
    incomplete = set()
    for path in sorted(scope.rglob("*")):
        if not path.is_file() or path.suffix not in YAML_SUFFIXES:
            continue
        if any(part.startswith(".") for part in path.relative_to(scope).parts):
            continue
        if path.stem == "main" and path.parent.name == "tasks":
            roles.add(path.parent.parent)
            continue
        keys, multi_document = yaml_shape(path.read_text())
        if keys & (PLAY_HEADERS | PLAY_BODY):
            playbooks.append(path)
            if multi_document or not keys & PLAY_HEADERS:
                incomplete.add(path)
    targets = sorted(roles) + [playbook for playbook in playbooks if not any(playbook.is_relative_to(role) for role in roles)]
    return targets, incomplete


def reference_values(node):
    if isinstance(node, yaml.ScalarNode):
        return [node.value]
    if isinstance(node, yaml.SequenceNode):
        return [item.value for item in node.value if isinstance(item, yaml.ScalarNode)]
    if isinstance(node, yaml.MappingNode):
        return [
            value.value for key, value in node.value
            if isinstance(key, yaml.ScalarNode) and key.value in {"file", "dir"}
            and isinstance(value, yaml.ScalarNode)
        ]
    return []


def literal_references(text):
    nodes = list(yaml.compose_all(text))
    seen = set()
    while nodes:
        node = nodes.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, yaml.SequenceNode):
            nodes.extend(node.value)
        elif isinstance(node, yaml.MappingNode):
            for key, value in node.value:
                nodes.append(value)
                if isinstance(key, yaml.ScalarNode) and key.value.rsplit(".", 1)[-1] in FILE_DIRECTIVES:
                    for reference in reference_values(value):
                        if reference and not any(marker in reference for marker in ("{{", "{%", "{#")):
                            yield reference


def referenced_paths(tree, targets):
    pending = []
    for target in targets:
        if target.is_file():
            pending.append(target)
        else:
            pending.extend(file for file in target.rglob("*") if file.is_file() and file.suffix in YAML_SUFFIXES)
    references = set()
    visited = set()
    while pending:
        source = pending.pop()
        if source in visited:
            continue
        visited.add(source)
        for reference in literal_references(source.read_text()):
            path = (source.parent / reference).resolve()
            if not path.is_relative_to(tree):
                continue
            references.add(path)
            if path.is_file() and path.suffix in YAML_SUFFIXES:
                pending.append(path)
    return references


def changed_scopes(workspace, scope, inventory):
    paths = git_paths(workspace, "diff", "--cached", "--no-renames", "--name-only", "-z")
    inventory_path = Path(os.path.normpath(inventory)) if inventory else None
    dependency_paths = set()
    if CONTENT_LOCK in git_paths(workspace, "ls-files", "-z", "--", str(CONTENT_LOCK)):
        dependencies = content_dependencies(git(workspace, "show", f":{CONTENT_LOCK}"))
        dependency_paths = {Path(os.path.normpath(item["archive"])) for item in dependencies}
    changed = []
    for path in paths:
        if path == inventory_path or path == CONTENT_LOCK or path in dependency_paths:
            return None
        if path.as_posix().endswith(CONFIG_NAMES + IGNORE_NAMES) or path.name == "ansible.cfg":
            return None
        if any(part.startswith(".") for part in path.parts):
            continue
        if path.is_relative_to(scope) and set(path.relative_to(scope).parts[:-1]) & DEPENDENCY_DIRS:
            return None
        if path.suffix in YAML_SUFFIXES:
            changed.append(path)
    return changed


def select_targets(tree, scope, staged_changes, workspace):
    targets, incomplete = lint_targets(scope)
    if staged_changes is None:
        return targets, incomplete
    paths = [tree / relative for relative in staged_changes]
    if all(path in targets for path in paths):
        return paths, incomplete
    references = referenced_paths(tree, targets)
    if any(path.resolve().is_relative_to(reference) for path in paths for reference in references):
        return targets, incomplete
    selected = []
    for relative, path in zip(staged_changes, paths, strict=True):
        if not path.is_relative_to(scope):
            continue
        if path in targets:
            selected.append(path)
            continue
        if path.is_file():
            text = path.read_text()
        else:
            before = subprocess.run(
                ["git", "-C", str(workspace), "show", f"HEAD:{relative}"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
            )
            text = before.stdout.decode() if before.returncode == 0 else ""
        keys, _ = yaml_shape(text)
        if looks_like_tasks(keys):
            # A task list, include or removed play can affect more than one target.
            return targets, incomplete
    return selected, incomplete


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
    if dependency["kind"] not in {"role", "collection"}:
        raise ValueError("Content requires a role or collection kind.")
    archive = contained_path(tree, dependency["archive"], "Content archive")
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != dependency["sha256"]:
            raise ValueError(f"Content archive checksum mismatch: {archive.relative_to(tree)}")
    with tarfile.open(archive) as bundle:
        roots = set()
        for member in bundle.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError(f"Unsafe path in content archive: {archive.relative_to(tree)}")
            if path.parts:
                roots.add(path.parts[0])
        if dependency["kind"] == "collection":
            manifest = bundle.extractfile("MANIFEST.json")
            metadata = json.load(manifest)["collection_info"] if manifest else {}
            if metadata.get("version") != dependency["version"]:
                raise ValueError(f"Collection manifest version mismatch: {archive.relative_to(tree)}")
            return archive, f"{metadata['namespace']}.{metadata['name']}"
        if len(roots) != 1:
            raise ValueError("A role archive must contain one named top-level role directory.")
        name = roots.pop()
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", name):
            raise ValueError(f"Invalid role archive name: {name}")
    return archive, name


def content_dependencies(contents):
    manifest = yaml.safe_load(contents)
    if not isinstance(manifest, dict) or set(manifest) != {"dependencies"} or not isinstance(manifest["dependencies"], list):
        raise ValueError("The Ansible content lock needs a dependencies list.")
    for dependency in manifest["dependencies"]:
        if not isinstance(dependency, dict) or set(dependency) != {"kind", "archive", "version", "sha256"}:
            raise ValueError("Each content lock entry needs kind, archive, version and sha256.")
        if not all(isinstance(value, str) and value for value in dependency.values()):
            raise ValueError("Content lock entries require nonempty strings.")
    return manifest["dependencies"]


def install_content(tree, scratch, env):
    lock = tree / CONTENT_LOCK
    if not lock.is_file():
        return
    installed = set()
    for dependency in content_dependencies(lock.read_bytes()):
        archive, name = locked_archive(tree, dependency)
        kind = dependency["kind"]
        key = (kind, name)
        if key in installed:
            raise ValueError(f"Duplicate locked {kind}: {name}")
        destination = scratch / ("collections" if kind == "collection" else "roles")
        arguments = [str(archive)]
        if kind == "role":
            requirements = scratch / "role-requirements.yml"
            requirements.write_text(yaml.safe_dump({
                "roles": [{"name": name, "src": str(archive), "version": dependency["version"]}],
            }))
            arguments = ["-r", str(requirements)]
        subprocess.run(
            [str(TOOL_BIN / "ansible-galaxy"), kind, "install", "--no-deps", "-p", str(destination), *arguments],
            cwd=scratch, env=env, check=True,
        )
        installed.add(key)


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
    inventory_input = os.environ.get("ANSIBLE_CI_FIXTURE_INVENTORY")
    changes = changed_scopes(workspace, scope, inventory_input) if args.staged else None
    if changes == []:
        return 0
    with tempfile.TemporaryDirectory() as temporary:
        scratch = Path(temporary)
        tree = scratch / "tree"
        tree.mkdir()
        snapshot(workspace, tree, args.staged)
        root = tree / scope
        targets, incomplete = select_targets(tree, root, changes, workspace)
        if not targets:
            if args.staged:
                return 0
            raise ValueError("No Ansible content in working-directory.")
        config = lint_config(tree, root, scratch)
        inventory = fixture_inventory(tree, inventory_input, scratch)
        env = isolated_environment(scratch, inventory, root)
        install_content(tree, scratch, env)
        # Native lint can classify an incomplete play as generic YAML.
        for target in targets:
            if target in incomplete:
                result = subprocess.run(
                    [str(TOOL_BIN / "ansible-playbook"), "--syntax-check", str(target)],
                    cwd=root, env=env, check=False,
                )
                if result.returncode:
                    raise ValueError(f"syntax-check failed: {target.relative_to(root)}")
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
