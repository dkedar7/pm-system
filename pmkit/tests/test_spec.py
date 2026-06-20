"""U6 tests — category CLI commands and the pm-spec skill/enforcement contract."""

from __future__ import annotations

from pathlib import Path

from pmkit.backlog import Backlog
from pmkit.cli import main

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "pm-spec" / "SKILL.md"
ENFORCE = ROOT / "skills" / "pm-spec" / "references" / "category-enforcement.md"


def _specced_item(db: str) -> int:
    bl = Backlog(db)
    opp = bl.add_candidate("o/r", "Add CLI flag", "users want a --json flag")
    bl.record_killtest(opp, [{"axis": "rarity", "verdict": "survive"}], survived=True)
    bl.promote(opp)  # -> specced
    bl.close()
    return opp


def test_cli_categorize_sets_category(tmp_path):
    db = str(tmp_path / "b.db")
    main(["backlog", "add", "--db", db, "--target", "o/r", "--title", "T"])
    assert main(["backlog", "categorize", "--db", db, "1",
                 "--category", "human-and-agent"]) == 0
    assert Backlog(db).get(1)["category"] == "human-and-agent"


def test_cli_categorize_rejects_bad_value(tmp_path, capsys):
    db = str(tmp_path / "b.db")
    main(["backlog", "add", "--db", db, "--target", "o/r", "--title", "T"])
    # argparse choices reject the value -> SystemExit(2)
    try:
        main(["backlog", "categorize", "--db", db, "1", "--category", "nonsense"])
        assert False, "should have exited"
    except SystemExit as e:
        assert e.code == 2


def test_cli_spec_requires_specced(tmp_path):
    db = str(tmp_path / "b.db")
    main(["backlog", "add", "--db", db, "--target", "o/r", "--title", "T"])  # status new
    assert main(["backlog", "spec", "--db", db, "1", "--path", "x.md"]) == 1


def test_cli_spec_records_path(tmp_path):
    db = str(tmp_path / "b.db")
    opp = _specced_item(db)
    assert main(["backlog", "spec", "--db", db, str(opp), "--path", "docs/x-requirements.md"]) == 0
    assert Backlog(db).get(opp)["spec_path"] == "docs/x-requirements.md"


def test_skill_and_enforcement_contract():
    skill = SKILL.read_text(encoding="utf-8")
    assert "name: pm-spec" in skill
    assert "category-enforcement" in skill  # skill points at the reference
    enforce = ENFORCE.read_text(encoding="utf-8")
    # R12/R13/R14 enforcement must be spelled out
    assert "agent-only" in enforce and "human-and-agent" in enforce
    assert "human-first" in enforce.lower()
    assert "parity" in enforce.lower()
    assert "categorize" in enforce  # tells the drafter to record the category
