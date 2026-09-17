from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("scenario", "failures", "syncs", "exit_code"),
    [
        ("vanilla", 0, 0, 77),
        ("cachyos-shelly", 0, 1, 77),
        ("cachyos-shelly", 1, 2, 77),
        ("cachyos-shelly", 3, 3, 1),
    ],
)
def test_signed_database_sync_retries_before_upgrade(
    tmp_path: Path, scenario: str, failures: int, syncs: int, exit_code: int
) -> None:
    """Run the real container script with only its engine and pacman stubbed.

    Stop deliberately at the upgrade boundary: persistent sync failures must
    never reach it, and retries must retain normal signature verification.
    """
    trace = tmp_path / "calls.json"
    trace.write_text("[]")
    programs = {
        "engine": '''
import os, subprocess, sys
args = sys.argv[1:]
assert any(arg.endswith(":/work:ro,Z") for arg in args)
env = dict(os.environ)
env["SCENARIO"] = next(arg.split("=", 1)[1] for arg in args if arg.startswith("SCENARIO="))
raise SystemExit(subprocess.call(args[args.index("bash"):], env=env))
''',
        "pacman": '''
import json, os, sys
from pathlib import Path
trace = Path(os.environ["PACMAN_TRACE"])
calls = json.loads(trace.read_text())
calls.append(sys.argv[1:])
trace.write_text(json.dumps(calls))
if sys.argv[1] in ("-Syu", "-Su"):
    raise SystemExit(77)
assert sys.argv[1:] == ["-Syy", "--noconfirm"]
raise SystemExit(1 if len(calls) <= int(os.environ["SYNC_FAILURES"]) else 0)
''',
        "sleep": "pass\n",
    }
    for name, body in programs.items():
        executable = tmp_path / name
        executable.write_text(f"#!{sys.executable}\n{body}")
        executable.chmod(0o755)

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["bash", str(root / "scripts/check-arch-package-build.sh"), scenario],
        cwd=root,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ.get('PATH', '')}",
            "PENGUIN_BURNER_CONTAINER_ENGINE": str(tmp_path / "engine"),
            "PACMAN_TRACE": str(trace),
            "SYNC_FAILURES": str(failures),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == exit_code, result.stdout + result.stderr
    expected = [["-Syy", "--noconfirm"]] * syncs
    if exit_code == 77:
        expected.append(["-Su" if scenario == "cachyos-shelly" else "-Syu", "--noconfirm"])
    assert json.loads(trace.read_text()) == expected
