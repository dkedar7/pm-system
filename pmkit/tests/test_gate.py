"""U7 tests — the human gate and delegation, at the CLI and contract level."""

from __future__ import annotations

from pathlib import Path

from pmkit.backlog import Backlog
from pmkit.cli import main

ROOT = Path(__file__).resolve().parents[2]
PM_RUN = ROOT / "skills" / "pm-run" / "SKILL.md"


def _approved_item(db: str, category="human-and-agent") -> int:
    bl = Backlog(db)
    opp = bl.add_candidate("o/r", "Add retries", "no retry logic")
    bl.record_killtest(opp, [{"axis": "rarity", "verdict": "survive"}], survived=True)
    bl.set_scores(opp, 100, 2, 0.8, 4)
    bl.set_category(opp, category)
    bl.promote(opp)
    bl.set_spec(opp, "docs/x-requirements.md")
    bl.approve(opp, note="ok")
    bl.close()
    return opp


def _specced_item(db: str) -> int:
    bl = Backlog(db)
    opp = bl.add_candidate("o/r", "T", "p")
    bl.record_killtest(opp, [{"axis": "rarity", "verdict": "survive"}], survived=True)
    bl.promote(opp)  # specced, not approved
    bl.close()
    return opp


def test_gate_blocks_delegating_unapproved_via_cli(tmp_path):
    db = str(tmp_path / "b.db")
    opp = _specced_item(db)
    assert main(["backlog", "delegate", "--db", db, str(opp)]) == 1
    assert Backlog(db).get(opp)["status"] == "specced"  # unchanged


def test_gate_blocks_delegating_new_item(tmp_path):
    db = str(tmp_path / "b.db")
    main(["backlog", "add", "--db", db, "--target", "o/r", "--title", "T"])
    assert main(["backlog", "delegate", "--db", db, "1"]) == 1


def test_approved_item_delegates_and_carries_category(tmp_path):
    db = str(tmp_path / "b.db")
    opp = _approved_item(db, category="human-and-agent")
    assert main(["backlog", "delegate", "--db", db, str(opp)]) == 0
    item = Backlog(db).get(opp)
    assert item["status"] == "delegated"
    assert item["delegation"]["category"] == "human-and-agent"
    assert item["delegation"]["spec_path"] == "docs/x-requirements.md"


def test_ship_closes_lifecycle(tmp_path):
    db = str(tmp_path / "b.db")
    opp = _approved_item(db)
    main(["backlog", "delegate", "--db", db, str(opp)])
    assert main(["backlog", "ship", "--db", db, str(opp)]) == 0
    assert Backlog(db).get(opp)["status"] == "shipped"


def test_pm_run_skill_documents_gate_and_panel():
    text = PM_RUN.read_text(encoding="utf-8")
    assert "pm-killtest" in text and "pm-reranker" in text
    assert "majority" in text.lower() and "3 of 4" in text
    assert "pmkit discover" in text
    assert "approve" in text and "delegate" in text
    assert "auto_gate" in text  # the deferred-autonomy contract is documented
