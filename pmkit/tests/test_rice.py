"""U5 tests — RICE composite, guards, ranking, and reranker persona contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from pmkit.rice import RiceError, compute_rice, rank

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"


def test_compute_rice_formula():
    # (reach * impact * confidence) / effort
    assert compute_rice(100, 2, 0.9, 2) == pytest.approx(90.0)
    assert compute_rice(10, 1, 0.5, 5) == pytest.approx(1.0)


def test_confidence_is_clamped():
    assert compute_rice(10, 1, 5.0, 1) == pytest.approx(10.0)  # clamped to 1.0
    assert compute_rice(10, 1, -1.0, 1) == pytest.approx(0.0)  # clamped to 0.0


def test_effort_must_be_positive():
    with pytest.raises(RiceError):
        compute_rice(10, 1, 1, 0)
    with pytest.raises(RiceError):
        compute_rice(10, 1, 1, -3)


def test_negative_reach_or_impact_rejected():
    with pytest.raises(RiceError):
        compute_rice(-1, 1, 1, 1)
    with pytest.raises(RiceError):
        compute_rice(1, -1, 1, 1)


def test_rank_orders_desc_none_last():
    items = [
        {"id": 1, "rice": 1.0},
        {"id": 2, "rice": 135.0},
        {"id": 3, "rice": None},
        {"id": 4, "rice": 10.0},
    ]
    assert [it["id"] for it in rank(items)] == [2, 4, 1, 3]


def test_reranker_persona_contract():
    text = (AGENTS_DIR / "pm-reranker.md").read_text(encoding="utf-8")
    assert "name: pm-reranker" in text
    for field in ('"reach"', '"impact"', '"confidence"', '"effort"'):
        assert field in text
