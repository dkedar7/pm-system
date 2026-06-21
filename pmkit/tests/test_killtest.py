"""Tests for the kill-test survival rule (already-solved is dispositive)."""

from __future__ import annotations

from pmkit.backlog import Backlog
from pmkit.cli import main
from pmkit.killtest import decide_survival


def v(axis, verdict, conf=1.0):
    return {"axis": axis, "verdict": verdict, "confidence": conf}


def test_confident_already_solved_is_dispositive():
    verdicts = [v("already-solved", "refute", 0.9), v("pain-is-rare", "survive"),
                v("infeasible", "survive"), v("won't-be-adopted", "survive")]
    survived, reason = decide_survival(verdicts)
    assert survived is False and "dispositive" in reason  # 1 refute, but it's already-solved


def test_dash_case_two_of_four_with_solved_now_auto_prunes():
    """The exact Dash->MCP case (2/4) that previously needed a manual override."""
    verdicts = [v("already-solved", "refute", 0.95), v("won't-be-adopted", "refute", 0.75),
                v("pain-is-rare", "survive"), v("infeasible", "survive")]
    survived, reason = decide_survival(verdicts)
    assert survived is False and "dispositive" in reason


def test_low_confidence_solved_not_dispositive():
    verdicts = [v("already-solved", "refute", 0.4), v("pain-is-rare", "survive"),
                v("infeasible", "survive"), v("won't-be-adopted", "survive")]
    assert decide_survival(verdicts)[0] is True  # conf<0.7 and only 1 refute


def test_streamlit_case_two_refutes_survives():
    """The Streamlit->MCP case: 0 solved, <3 refutes -> a real opportunity survives."""
    verdicts = [v("pain-is-rare", "refute"), v("infeasible", "refute"),
                v("already-solved", "survive"), v("won't-be-adopted", "survive")]
    assert decide_survival(verdicts)[0] is True


def test_majority_prunes_without_solved():
    verdicts = [v("pain-is-rare", "refute"), v("infeasible", "refute"),
                v("won't-be-adopted", "refute"), v("already-solved", "survive")]
    survived, reason = decide_survival(verdicts)
    assert survived is False and "majority" in reason


def test_cli_killtest_decide_prunes_on_solved(tmp_path):
    db = str(tmp_path / "b.db")
    main(["backlog", "add", "--db", db, "--target", "o/r", "--title", "Already shipped"])
    verdicts = '[{"axis":"already-solved","verdict":"refute","confidence":0.95}]'
    rc = main(["backlog", "killtest", "--db", db, "1", "--decide", "--verdicts", verdicts])
    assert rc == 0 and Backlog(db).get(1)["status"] == "pruned"
