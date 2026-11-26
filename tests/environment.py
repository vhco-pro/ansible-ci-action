"""Observe the exact environment passed to the real linter during a fixture run."""
import os
import runpy
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

os.environ.update(
    AWS_ACCESS_KEY_ID="synthetic-sentinel",
    ANSIBLE_CONFIG="/fixture/operator.cfg",
    ANSIBLE_INVENTORY="/fixture/operator.yml",
)
main = runpy.run_path(sys.argv.pop(1))["main"]
real_run = subprocess.run
observed = False


def check_environment(*args, **kwargs):
    global observed
    if Path(args[0][0]).name == "ansible-lint":
        env = kwargs["env"]
        assert "AWS_ACCESS_KEY_ID" not in env
        assert env["ANSIBLE_CONFIG"] != "/fixture/operator.cfg"
        assert env["ANSIBLE_INVENTORY"] != "/fixture/operator.yml"
        assert env["ANSIBLE_INVENTORY_ENABLED"] == "yaml,ini"
        assert "localhost" in Path(env["ANSIBLE_INVENTORY"]).read_text()
        observed = True
    return real_run(*args, **kwargs)


with patch.object(subprocess, "run", check_environment):
    assert main() == 0
assert observed
