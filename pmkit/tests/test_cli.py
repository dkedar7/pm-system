"""U2 tests — CLI surface (entry wiring, --json after subcommand, error exits)."""

from __future__ import annotations

import json

from pmkit.cli import main


def test_add_list_status_roundtrip(tmp_path, capsys):
    db = str(tmp_path / "b.db")
    assert main(["backlog", "add", "--db", db, "--target", "o/r",
                 "--title", "Smoke", "--problem", "no retry"]) == 0
    capsys.readouterr()
    # --json must work *after* the subcommand
    assert main(["backlog", "list", "--db", db, "--json"]) == 0
    out = capsys.readouterr().out
    items = json.loads(out)
    assert len(items) == 1 and items[0]["title"] == "Smoke"
    assert main(["backlog", "status", "--db", db]) == 0


def test_promote_new_item_errors(tmp_path, capsys):
    db = str(tmp_path / "b.db")
    main(["backlog", "add", "--db", db, "--target", "o/r", "--title", "T"])
    capsys.readouterr()
    # a 'new' item can't be promoted; CLI returns nonzero, not a traceback
    assert main(["backlog", "promote", "--db", db, "1"]) == 1


def test_show_missing_returns_1(tmp_path):
    db = str(tmp_path / "b.db")
    assert main(["backlog", "show", "--db", db, "999"]) == 1
