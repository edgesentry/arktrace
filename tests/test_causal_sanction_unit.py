"""Unit tests for causal_sanction.py — no database required."""

from __future__ import annotations

from pipeline.src.score.causal_sanction import CausalEffect, effects_to_dataframe


def _make_effect(regime: str, mmsis: list[str]) -> CausalEffect:
    return CausalEffect(
        regime=regime,
        label=f"Label {regime}",
        n_treated=len(mmsis),
        n_control=10,
        att_estimate=1.5,
        att_ci_lower=0.5,
        att_ci_upper=2.5,
        p_value=0.01,
        is_significant=True,
        calibrated_weight=0.40,
        treated_mmsis=mmsis,
    )


def test_effects_to_dataframe_expands_per_vessel():
    effects = [
        _make_effect("OFAC_Iran", ["111111111", "222222222"]),
        _make_effect("OFAC_Russia", ["333333333"]),
    ]
    df = effects_to_dataframe(effects)
    assert df.height == 3
    assert set(df["mmsi"].to_list()) == {"111111111", "222222222", "333333333"}


def test_effects_to_dataframe_mmsi_column_present():
    df = effects_to_dataframe([_make_effect("OFAC_Iran", ["123456789"])])
    assert "mmsi" in df.columns
    assert df["mmsi"][0] == "123456789"


def test_effects_to_dataframe_regime_propagated_to_each_vessel():
    effects = [_make_effect("OFAC_Iran", ["111", "222"])]
    df = effects_to_dataframe(effects)
    assert df["regime"].to_list() == ["OFAC_Iran", "OFAC_Iran"]


def test_effects_to_dataframe_empty_effects_returns_correct_schema():
    df = effects_to_dataframe([])
    assert df.height == 0
    assert "mmsi" in df.columns
    assert "regime" in df.columns
    assert "att_estimate" in df.columns


def test_effects_to_dataframe_no_treated_vessels_returns_empty():
    df = effects_to_dataframe([_make_effect("OFAC_Iran", [])])
    assert df.height == 0


def test_effects_to_dataframe_att_values_match_regime():
    effect = _make_effect("OFAC_Iran", ["111", "222"])
    effect.att_estimate = 2.7
    df = effects_to_dataframe([effect])
    assert all(v == 2.7 for v in df["att_estimate"].to_list())
