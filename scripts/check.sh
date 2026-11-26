#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python=${ANSIBLE_CI_PYTHON:?Point ANSIBLE_CI_PYTHON to the prepared virtual environment.}
versions=$("$script_dir/setup.sh" versions)
"$python" -I "$script_dir/check.py" "$@"
if [[ -n ${GITHUB_OUTPUT:-} ]]; then printf '%s\n' "$versions" >> "$GITHUB_OUTPUT"; fi
