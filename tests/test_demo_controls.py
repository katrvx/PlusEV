"""The live risk-controls demo (scripts/demo_controls.py) runs offline, passes, and fails loudly when a control
is broken. Run: python3 -m pytest -q tests/test_demo_controls.py"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "demo_controls.py"


@pytest.fixture(scope="module")
def demo():
    spec = importlib.util.spec_from_file_location("demo_controls", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PHRASES = {
    1: ["[1] Sealed holdout", "'the test split is sealed'", "split=test status=refused", "holdout_accessed=True",
        "HoldoutAccessError"],
    2: ["[2] No invented numbers", "REJECTED by the output validator", "not copied from the cited evidence",
        "'-0.0350'", "ACCEPTED after"],
    3: ["[3] Pre-registered rule", "verdict=approve_for_frozen_test", "does not beat cash", "verdict=INCONCLUSIVE",
        "champion=None"],
    4: ["[4] One sealed look", "REFUSED: AlreadyLooked", "spec_dbd7812c913a", "ledger unchanged: True",
        "kok_a.experiment imported: False"],
}


def test_default_run_passes_every_control(demo, capsys):
    assert demo.main([]) == 0
    out = capsys.readouterr().out
    for phrases in PHRASES.values():
        for p in phrases:
            assert p in out, p
    assert out.count("  PASS  ") == 4 and "FAIL" not in out
    assert "4 controls, all enforced in code, every attempt logged." in out
    assert "\033[" not in out                       # no ANSI when not a terminal


def test_only_runs_one_control(demo, capsys):
    assert demo.main(["--only", "4", "--plain"]) == 0
    out = capsys.readouterr().out
    assert "[4] One sealed look" in out and "[1]" not in out and "1 control, all enforced in code" in out


def test_a_broken_control_makes_the_demo_fail(demo, capsys, monkeypatch):
    from packages.research_agents import frozen
    monkeypatch.setattr(frozen, "check", lambda *a, **k: None)      # simulate a ledger that lets a 2nd look through
    assert demo.main(["--only", "4"]) == 1
    out = capsys.readouterr().out
    assert "ALLOWED" in out and "did NOT behave as expected: [4]" in out


def test_cli_exit_code_from_repo_root_without_api_keys():
    env = {k: v for k, v in os.environ.items() if "API_KEY" not in k and k != "KOK_AGENT_MODEL"}
    r = subprocess.run([sys.executable, str(SCRIPT), "--only", "1", "--plain"], cwd=ROOT, capture_output=True,
                       text=True, timeout=60, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "holdout_accessed=True" in r.stdout and "[agents]" not in r.stderr
