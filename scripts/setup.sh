#!/usr/bin/env bash
set -euo pipefail

fail() { printf '%s\n' "$*" >&2; exit 1; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || fail 'Supported platform: Linux x64.'
version=$(awk '$1 == "python" { print $2 }' "$script_dir/.tool-versions")
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'Missing or invalid Python pin.'
mode=${1:-}
case "$mode" in
  pin) printf '%s\n' "$version"; exit 0 ;;
  versions)
    python=${ANSIBLE_CI_PYTHON:?Point ANSIBLE_CI_PYTHON to the prepared virtual environment.}
    "$python" -I - "$version" "$script_dir/requirements.txt" <<'PY'
import importlib.metadata
import platform
import sys
from pathlib import Path

version, lock = sys.argv[1:]
if platform.python_version() != version:
    raise SystemExit(f"Python {version} is required.")
print(f"python-version={version}")
pins = Path(lock).read_text().splitlines()
for name in ("ansible-core", "ansible-lint"):
    pin = next((line.split()[0].split("==", 1)[1] for line in pins if line.startswith(name + "==")), None)
    actual = importlib.metadata.version(name)
    if actual != pin:
        raise SystemExit(f"{name} {pin} is required, found {actual}.")
    print(f"{name}-version={actual}")
PY
    exit 0 ;;
  install) ;;
  *) fail 'Usage: setup.sh pin|versions, or setup.sh install DESTINATION [ARCHIVE].' ;;
esac

destination=$(realpath -m -- "${2:?Installation destination required}")
IFS=$'\t' read -r build checksum < "$script_dir/python-archive.tsv"
[[ $build =~ ^[0-9]{8}$ && $checksum =~ ^[0-9a-f]{64}$ ]] || fail 'Invalid Python archive pin.'
scratch=$(mktemp -d)
owned=false
complete=false
cleanup() {
  rm -rf -- "$scratch"
  if [[ $owned == true && $complete == false ]]; then rm -rf -- "$destination"; fi
}
trap cleanup EXIT
mkdir -p "$scratch/home"
asset="cpython-$version+$build-x86_64-unknown-linux-gnu-install_only.tar.gz"
archive=${3:-$scratch/$asset}
if [[ $# -lt 3 ]]; then
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
    --retry 2 --connect-timeout 15 --max-time 180 --output "$archive" \
    "https://github.com/astral-sh/python-build-standalone/releases/download/$build/$asset"
fi
actual=$(sha256sum -- "$archive")
[[ ${actual%% *} == "$checksum" ]] || fail "Python $version archive checksum mismatch."
mkdir -- "$destination"
owned=true
tar -xzf "$archive" -C "$destination"
run() { env -i PATH=/usr/bin:/bin HOME="$scratch/home" PIP_CONFIG_FILE=/dev/null "$@"; }
run "$destination/python/bin/python3" -I -m venv "$destination/venv"
run "$destination/venv/bin/python" -I -m pip --isolated --disable-pip-version-check install \
  --no-cache-dir --require-hashes --only-binary=:all: --index-url https://pypi.org/simple \
  -r "$script_dir/requirements.txt"
ANSIBLE_CI_PYTHON="$destination/venv/bin/python" "$script_dir/setup.sh" versions
complete=true
