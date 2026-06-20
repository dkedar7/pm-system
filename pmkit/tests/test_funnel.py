"""U8 tests — killtest/score CLI commands and the pm-funnel workflow contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from pmkit.backlog import Backlog
from pmkit.cli import main

WF = Path(__file__).resolve().parents[2] / "workflows" / "pm-funnel.js"


# ---------------------------------------------------------------- CLI: killtest
def test_cli_killtest_prunes(tmp_path):
    db = str(tmp_path / "b.db")
    main(["backlog", "add", "--db", db, "--target", "o/r", "--title", "T"])
    assert main(["backlog", "killtest", "--db", db, "1", "--pruned"]) == 0
    assert Backlog(db).get(1)["status"] == "pruned"


def test_cli_killtest_survives_and_stores_verdicts(tmp_path):
    db = str(tmp_path / "b.db")
    main(["backlog", "add", "--db", db, "--target", "o/r", "--title", "T"])
    verdicts = '[{"axis": "infeasible", "verdict": "survive"}]'
    assert main(["backlog", "killtest", "--db", db, "1", "--survived",
                 "--verdicts", verdicts]) == 0
    item = Backlog(db).get(1)
    assert item["status"] == "survived"
    assert item["killtest"][0]["axis"] == "infeasible"


def test_cli_killtest_requires_a_choice(tmp_path):
    db = str(tmp_path / "b.db")
    main(["backlog", "add", "--db", db, "--target", "o/r", "--title", "T"])
    with pytest.raises(SystemExit) as e:  # mutually-exclusive group is required
        main(["backlog", "killtest", "--db", db, "1"])
    assert e.value.code == 2


def test_cli_killtest_bad_json(tmp_path):
    db = str(tmp_path / "b.db")
    main(["backlog", "add", "--db", db, "--target", "o/r", "--title", "T"])
    assert main(["backlog", "killtest", "--db", db, "1", "--survived",
                 "--verdicts", "{not json"]) == 1


# ------------------------------------------------------------------- CLI: score
def _survived(db: str) -> int:
    main(["backlog", "add", "--db", db, "--target", "o/r", "--title", "T"])
    main(["backlog", "killtest", "--db", db, "1", "--survived"])
    return 1


def test_cli_score_sets_rice(tmp_path):
    db = str(tmp_path / "b.db")
    opp = _survived(db)
    assert main(["backlog", "score", "--db", db, str(opp),
                 "--reach", "100", "--impact", "2", "--confidence", "0.8", "--effort", "4"]) == 0
    assert Backlog(db).get(opp)["rice"] == pytest.approx(40.0)


def test_cli_score_zero_effort_errors(tmp_path):
    db = str(tmp_path / "b.db")
    opp = _survived(db)
    assert main(["backlog", "score", "--db", db, str(opp),
                 "--reach", "1", "--impact", "1", "--confidence", "1", "--effort", "0"]) == 1


# ------------------------------------------------------ workflow script contract
def test_workflow_script_structure():
    text = WF.read_text(encoding="utf-8")
    assert "name: 'pm-funnel'" in text
    for title in ("Discover", "Stress-test", "Rank"):
        assert title in text
    for ag in ("pm-killtest-solved", "pm-killtest-rarity", "pm-killtest-feasibility",
               "pm-killtest-adoption", "pm-reranker"):
        assert ag in text
    assert "pmkit discover" in text
    assert "pmkit backlog killtest" in text and "pmkit backlog score" in text
    assert "PRUNE_AT = 3" in text and "refutes < PRUNE_AT" in text
    assert "nothing new" in text          # zero-candidate short-circuit
    assert "pipeline(" in text and "parallel(" in text
    assert ".filter(Boolean)" in text     # degrade past a dead kill-test agent


def test_workflow_avoids_forbidden_apis():
    text = WF.read_text(encoding="utf-8")
    assert "Date.now" not in text and "Math.random" not in text
