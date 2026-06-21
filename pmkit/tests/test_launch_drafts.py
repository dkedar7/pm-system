"""U7 tests — draft starting-points, slop-critic flags, and the never-final guardrail."""

from __future__ import annotations

import json

from pmkit.cli import main
from pmkit.launch.drafts import DRAFT_KIND, emit, record_draft
from pmkit.launch.store import LaunchStore


def _store(tmp_path):
    return LaunchStore(tmp_path / "b.db")


# --- structural never-final guardrail ---
def test_stored_draft_is_always_starting_point(tmp_path):
    with _store(tmp_path) as st:
        record_draft(st, "p", "reddit", "rough draft text", community="r/gis")
        drafts = st.list_drafts("p")
    assert drafts[0]["kind"] == DRAFT_KIND == "starting_point"


def test_no_api_or_column_can_mark_a_draft_final(tmp_path):
    with _store(tmp_path) as st:
        # No method exists to mark a draft final/postable/ready.
        for forbidden in ("set_final", "mark_postable", "finalize_draft", "mark_ready"):
            assert not hasattr(st, forbidden)
        # And the table has no status/final/postable column to set.
        cols = {r[1] for r in st.conn.execute("PRAGMA table_info(launch_drafts)").fetchall()}
    assert not (cols & {"status", "final", "postable", "ready"})
    assert "kind" in cols  # the only state, and it's fixed to starting_point


# --- slop-critic surfacing ---
def test_flagged_draft_surfaces_on_emit(tmp_path):
    critic = {"flagged": True, "score": 0.8,
              "tells": ["excited to announce", "game-changer"],
              "suggestion": "lead with the actual demo"}
    with _store(tmp_path) as st:
        record_draft(st, "p", "linkedin", "Excited to announce my game-changer!", critic=critic)
        drafts = st.list_drafts("p")
    out = emit(drafts)
    assert "FLAGGED" in out
    assert "excited to announce" in out
    assert "lead with the actual demo" in out


def test_emit_labels_everything_starting_point(tmp_path):
    with _store(tmp_path) as st:
        record_draft(st, "p", "reddit", "some text")
        drafts = st.list_drafts("p")
    out = emit(drafts)
    assert "STARTING-POINT" in out
    assert "never paste as-is" in out.lower() or "rewrite" in out.lower()


def test_emit_empty():
    assert "(no drafts)" in emit([])


# --- CLI ---
def test_cli_draft_record_and_list_json(tmp_path, capsys):
    db = str(tmp_path / "b.db")
    critic = json.dumps({"flagged": False, "score": 0.1, "tells": [], "suggestion": ""})
    rc = main(["launch", "draft", "--product", "streamlit-mcp", "--platform", "hackernews",
               "--text", "Show HN: I made X", "--critic", critic, "--db", db])
    assert rc == 0
    capsys.readouterr()  # flush the record command's human output before the JSON read
    rc = main(["launch", "drafts", "--product", "streamlit-mcp", "--json", "--db", db])
    assert rc == 0
    drafts = json.loads(capsys.readouterr().out)
    assert drafts[0]["kind"] == "starting_point"
    assert drafts[0]["critic_flagged"] is False
