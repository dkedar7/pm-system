"""U2 tests — clean-room install runner."""

from __future__ import annotations

import sys

from pmkit.dogfood.install import run_documented_install

PY = sys.executable or "python"


def test_successful_steps_all_ok():
    rep = run_documented_install([f'{PY} -c "print(1)"'])
    assert rep.all_ok is True
    assert len(rep.steps) == 1 and rep.steps[0].ok and rep.gaps == []


def test_failed_step_is_gap_not_crash():
    """R3: a documented command that fails is a gap, not an exception."""
    rep = run_documented_install([f'{PY} -c "import sys; sys.exit(3)"'])
    assert rep.all_ok is False
    s = rep.steps[0]
    assert s.gap is True and s.exit_code == 3 and "exit 3" in s.reason


def test_run_continues_past_failure():
    rep = run_documented_install([
        f'{PY} -c "import sys; sys.exit(1)"',   # fails
        f'{PY} -c "print(\'after\')"',          # still runs
    ])
    assert len(rep.steps) == 2
    assert rep.steps[0].gap is True
    assert rep.steps[1].ok is True and "after" in rep.steps[1].output


def test_timeout_is_gap():
    rep = run_documented_install([f'{PY} -c "import time; time.sleep(5)"'], timeout=1)
    assert rep.steps[0].gap is True and "timeout" in rep.steps[0].reason


def test_unspawnable_command_is_gap():
    rep = run_documented_install(["this-command-does-not-exist-xyz --nope"])
    assert rep.steps[0].gap is True and rep.steps[0].ok is False


def test_to_dict_shape():
    rep = run_documented_install([f'{PY} -c "print(1)"'])
    d = rep.to_dict()
    assert d["all_ok"] is True and d["steps"][0]["command"]
