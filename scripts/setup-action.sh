#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
scratch=$(mktemp -d "${RUNNER_TEMP:?Missing RUNNER_TEMP}/ansible-ci.XXXXXXXX")
"$script_dir/setup.sh" install "$scratch/tools"
printf 'python=%s\n' "$scratch/tools/venv/bin/python" >> "$GITHUB_OUTPUT"
