"""The checks Lane A is not allowed to skip: fill lag, no future inputs, switching costs, sealed holdout, missingness."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from kok_a.binance import normalize_binance_epoch, read_binance_klines
from kok_a.experiment import (
    N_BOOT,
    GateRunner,
    _compound,
    _cost_row,
    _fit_lgbm,
    agent_view,
    assemble,
)
from kok_a.regimes import discover_regime_filter, fit_regime_labels
from kok_a.features import (
    MARKET_FEATURES,
    TemporalLeakError,
    asof_fear_greed,
    asof_news,
    assert_point_in_time,
    build_frame,
    market_features,
    with_execution,
)
from kok_a.arbiter import DRAWDOWN_CAP, MIN_TEST_DECISIONS, build_paper_plan, decide
from kok_a.contracts import Decision, GateEvaluation, Metrics
from kok_a.gates import allocation, regime_gate_allocation, rule_gate_spec
from kok_a.lgbm_gate import BAND, LGBMGate
from kok_a.market import hash_ohlcv, synthetic_ohlcv
from kok_a.snapshot import (
    FEAR_GREED_PATH,
    FIVE_MIN_MANIFEST_PATH,
    FIVE_MIN_PATH,
    MANIFEST_PATH,
    OHLCV_PATH,
    SNAPSHOT_READY,
    read_fear_greed,
)
from kok_a.simulate import COST_PER_UNIT, simulate
from kok_a.strategies import positions


def _bars(opens: list[float], closes: list[float]) -> pd.DataFrame:
    start = pd.Timestamp("2024-01-01", tz="UTC")
    n = len(opens)
    return pd.DataFrame(
        {
            "open_time": start + pd.to_timedelta(np.arange(n), unit="h"),
            "open": opens,
            "high": np.maximum(opens, closes),
            "low": np.minimum(opens, closes),
            "close": closes,
            "volume": np.ones(n),
            "symbol": "BTCUSDT",
            "venue": "fixture",
        }
    )


def test_binance_timestamps_normalise_seconds_milliseconds_microseconds():
    ms = 1_700_000_000_000
    assert normalize_binance_epoch(1_700_000_000) == ms
    assert normalize_binance_epoch(ms) == ms
    assert normalize_binance_epoch(ms * 1000) == ms


def test_binance_csv_reader_accepts_both_archive_units(tmp_path):
    ms = 1_700_000_000_000
    expected = pd.Timestamp(ms, unit="ms", tz="UTC")
    for stamp in (ms, ms * 1000):
        path = tmp_path / f"{stamp}.csv"
        path.write_text(f"{stamp},100,110,90,105,12\n")
        frame = read_binance_klines(path)
        assert frame.loc[0, "open_time"] == expected
        assert frame.loc[0, "close"] == 105


def test_fill_uses_next_open_not_the_same_bar_close():
    # Bar 2 closes at 500. The position decided there fills at the next open, 110,
    # and earns the move to the open after that, which is also 110.
    bars = _bars(
        opens=[100, 100, 100, 110, 110, 121],
        closes=[100, 100, 500, 110, 110, 121],
    )
    executed = with_execution(bars)
    spike = executed.loc[executed["bar_index"] == 2].iloc[0]
    assert spike["close"] == 500
    assert spike["fill_open"] == 110
    assert spike["fill_open"] != spike["close"]
    assert spike["ret_next"] == pytest.approx(0.0)
    later = executed.loc[executed["bar_index"] == 3].iloc[0]
    assert later["ret_next"] == pytest.approx(121 / 110 - 1)


def test_features_do_not_move_when_a_future_close_does():
    bars = synthetic_ohlcv(300, seed=1)
    original = market_features(bars)
    bumped = bars.copy()
    bumped.loc[bumped.index[-1], "close"] *= 5
    changed = market_features(bumped)
    for column in MARKET_FEATURES:
        assert original.iloc[-2][column] == pytest.approx(changed.iloc[-2][column])
    assert original.iloc[-1]["momentum_24h"] != pytest.approx(changed.iloc[-1]["momentum_24h"])
    close = bars["close"]
    by_hand = float(np.log(close.iloc[200] / close.iloc[176]))
    assert original.iloc[200]["momentum_24h"] == pytest.approx(by_hand)


def test_a_feature_timestamped_after_the_decision_is_rejected():
    frame = build_frame(synthetic_ohlcv(220, seed=2))
    leaked = frame.copy()
    leaked.loc[0, "data_max_available_at"] = leaked.loc[0, "decision_time"] + pd.Timedelta(hours=1)
    with pytest.raises(TemporalLeakError):
        assert_point_in_time(leaked)


def test_fear_greed_is_not_visible_before_its_publication():
    decisions = pd.to_datetime(["2023-01-02 12:00", "2023-01-03 00:00"], utc=True)
    daily = pd.DataFrame(
        {
            "available_at": pd.to_datetime(["2023-01-03 00:00"], utc=True),
            "value": [99.0],
        }
    )
    joined = asof_fear_greed(decisions, daily)
    assert pd.isna(joined["value"].iloc[0])
    assert joined["value"].iloc[1] == 99.0


def test_news_is_not_filled_in_before_it_is_first_seen():
    decisions = pd.to_datetime(["2023-01-02 00:00", "2023-01-03 00:00", "2023-01-05 00:00"], utc=True)
    items = pd.DataFrame(
        {
            "first_seen_at": pd.to_datetime(["2023-01-03 00:00"], utc=True),
            "sentiment": [0.8],
        }
    )
    sentiment, _available = asof_news(decisions, items)
    assert np.isnan(sentiment[0])
    assert sentiment[1] == pytest.approx(0.8)
    assert np.isnan(sentiment[2])  # older than the 24h window; left missing, not carried forward


def test_a_policy_that_flips_pays_more_than_one_that_holds():
    n = 12
    frame = pd.DataFrame(
        {
            "target_position": np.ones(n),
            "ret_next": np.zeros(n),
            "split": ["train"] * n,
        }
    )
    held = simulate(frame, pd.Series(1.0, index=frame.index))
    flipped = simulate(frame, pd.Series([1.0, 0.0] * (n // 2)))
    assert held["cost"].sum() == pytest.approx(COST_PER_UNIT)
    assert flipped["fees"].sum() > held["fees"].sum()


def test_snapshot_and_both_demo_strategies_are_deterministic():
    first = synthetic_ohlcv(400, seed=7)
    second = synthetic_ohlcv(400, seed=7)
    assert hash_ohlcv(first) == hash_ohlcv(second)
    _, trend = positions("btc-trend-24-72-demo", first["close"])
    _, trend_again = positions("btc-trend-24-72-demo", first["close"])
    _, meanrev = positions("btc-meanrev-48-demo", first["close"])
    assert trend.equals(trend_again)
    assert not np.allclose(trend.fillna(0), meanrev.fillna(0))
    assert meanrev.dropna().isin([0.0, 1.0]).all()


def test_runner_refuses_the_sealed_split_and_train_ignores_test_labels(bundle):
    spec = {"policy_id": "always_on", "family": "always_on"}
    with pytest.raises(PermissionError):
        bundle.runner.evaluate(spec, "test")
    runner = GateRunner(
        bundle.frame.copy(),
        bundle.lgbm,
        seed=1,
        n_boot=10,
        snapshot_id="x",
        thresholds=bundle.thresholds,
    )
    before = runner.evaluate(spec, "train")
    runner.frame.loc[runner.frame["split"] == "test", "ret_next"] = 123.0
    after = runner.evaluate(spec, "train")
    assert after.metrics.net_return == pytest.approx(before.metrics.net_return)


def test_lightgbm_refuses_to_fit_or_calibrate_outside_train():
    gate = LGBMGate()
    for split in ("validation", "test"):
        with pytest.raises(PermissionError):
            gate.fit(pd.DataFrame(), pd.Series(dtype=float), split=split)
        with pytest.raises(PermissionError):
            gate.calibrate(pd.DataFrame(), pd.Series(dtype=float), split=split)


def test_frozen_holdout_is_cached_and_a_changed_policy_is_refused(bundle):
    runner = GateRunner(
        bundle.frame.copy(),
        bundle.lgbm,
        seed=3,
        n_boot=10,
        snapshot_id="x",
        thresholds=bundle.thresholds,
    )
    spec = {"policy_id": "frozen::always", "family": "always_on"}
    first = runner.evaluate_frozen(spec)
    assert first.metrics.net_return != pytest.approx(0.0)
    runner.frame.loc[runner.frame["split"] == "test", "ret_next"] = 0.0
    second = runner.evaluate_frozen(spec)
    assert second.metrics.net_return == pytest.approx(first.metrics.net_return)
    changed = {"policy_id": "frozen::always", "family": "cash"}
    with pytest.raises(PermissionError):
        runner.evaluate_frozen(changed)


def test_rule_threshold_and_regime_cuts_come_from_train_only(bundle):
    train = bundle.frame[bundle.frame["split"] == "train"]
    spec = rule_gate_spec(train)
    vol_cut = spec["conditions"][1]["threshold"]
    assert vol_cut == pytest.approx(float(train["realized_vol_7d"].median()))
    assert spec["conditions"][0]["threshold"] == 0.0
    poisoned = bundle.frame.copy()
    poisoned.loc[poisoned["split"] == "test", "realized_vol_7d"] *= 10
    poisoned.loc[poisoned["split"] == "test", "momentum_24h"] += 1
    assert rule_gate_spec(poisoned[poisoned["split"] == "train"])["conditions"][1]["threshold"] == pytest.approx(vol_cut)
    _, cuts = fit_regime_labels(poisoned)
    assert cuts["momentum_terciles"] == pytest.approx(bundle.thresholds["momentum_terciles"])
    assert cuts["vol_median"] == pytest.approx(bundle.thresholds["vol_median"])


def test_splits_are_chronological_and_do_not_overlap(bundle):
    windows = {window.split: window for window in bundle.result.windows}
    assert windows["train"].end < windows["validation"].start
    assert windows["validation"].end < windows["test"].start
    stamps = bundle.frame["decision_time"]
    train = set(stamps[bundle.frame["split"] == "train"])
    valid = set(stamps[bundle.frame["split"] == "validation"])
    test = set(stamps[bundle.frame["split"] == "test"])
    assert train.isdisjoint(valid)
    assert valid.isdisjoint(test)
    assert train.isdisjoint(test)


def test_missingness_report_matches_the_frame_and_news_is_not_complete(bundle):
    result = bundle.result
    train = bundle.frame[bundle.frame["split"] == "train"]
    for name, share in result.missingness["train"].items():
        assert share == pytest.approx(float(train[name].notna().mean()))
    assert result.coverage == result.missingness["train"]
    assert result.coverage["momentum_24h"] == 1.0
    assert result.coverage["news_sentiment"] == 0.0
    assert result.coverage["fear_greed"] == 1.0
    assert result.provenance["prices"] == "synthetic"
    assert result.provenance["news"] == "omitted"
    assert train["news_sentiment"].isna().all()
    assert (bundle.frame["fill_open"] != bundle.frame["close"]).mean() > 0.99


def test_preregistered_baselines_exist_on_every_split_including_holdout(bundle):
    result = bundle.result
    present = {(row.split, row.policy) for row in result.baselines}
    for split in ("train", "validation", "test"):
        for policy in ("always_on", "cash", "simple_rule", "regime_filter", "lgbm_gate"):
            assert (split, policy) in present
    cash = next(row for row in result.baselines if row.split == "test" and row.policy == "cash")
    assert cash.metrics.net_return == pytest.approx(0.0, abs=1e-12)
    assert cash.metrics.exposure == pytest.approx(0.0)
    always = next(row for row in result.baselines if row.split == "train" and row.policy == "always_on")
    assert 0.0 < always.metrics.exposure <= 1.0
    assert always.metrics.n_switches > 1
    assert bundle.lgbm.fitted_on == "train"
    assert bundle.lgbm.calibrated_on == "train_tail"
    assert any(row.regime_feature == "trend_regime" and row.bucket == "bull" for row in result.per_regime)
    assert {row.bucket for row in result.per_regime if row.regime_feature == "trend_regime"} >= {"bull", "bear", "sideways"}


def test_market_hash_does_not_depend_on_pandas_datetime_resolution():
    bars = read_binance_klines(OHLCV_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text())
    as_us = bars.copy()
    as_ns = bars.copy()
    stamps = pd.to_datetime(bars["open_time"], utc=True)
    as_us["open_time"] = stamps.dt.as_unit("us")
    as_ns["open_time"] = stamps.dt.as_unit("ns")
    assert str(as_us["open_time"].dtype) != str(as_ns["open_time"].dtype)
    assert hash_ohlcv(as_us) == hash_ohlcv(as_ns) == manifest["market_hash"]


def test_ready_snapshot_is_real_binance_and_fear_greed_with_no_invented_news():
    manifest = json.loads(MANIFEST_PATH.read_text())
    bars = read_binance_klines(OHLCV_PATH)
    fear = read_fear_greed(FEAR_GREED_PATH)
    assert manifest["id"] == SNAPSHOT_READY
    assert manifest["n_bars"] == 76559
    assert manifest["n_gaps_over_1h"] == 26
    assert bars["venue"].iloc[0] == "binance_spot"
    assert hash_ohlcv(bars) == manifest["market_hash"]
    assert bars["open_time"].iloc[0] == pd.Timestamp("2018-02-01", tz="UTC")
    assert bars["open_time"].iloc[-1] == pd.Timestamp("2026-10-31 23:00", tz="UTC")
    spacing = bars["open_time"].diff().dropna()
    assert (spacing == pd.Timedelta(hours=1)).sum() == len(spacing) - 26
    assert (fear["value"] == fear["value"].round()).all()
    assert fear["source"].str.contains("Alternative.me").all()

    frame = build_frame(bars, fear_greed=fear)
    noon = frame.loc[frame["decision_time"] == pd.Timestamp("2024-11-01 12:00", tz="UTC")].iloc[0]
    published_yesterday = fear.loc[fear["as_of_day"] == pd.Timestamp("2024-10-31", tz="UTC")].iloc[0]
    published_today = fear.loc[fear["as_of_day"] == pd.Timestamp("2024-11-01", tz="UTC")].iloc[0]
    assert noon["fear_greed"] == published_yesterday["value"]
    assert noon["fear_greed_available_at"] == published_yesterday["available_at"]
    assert published_today["available_at"] > noon["decision_time"]
    assert frame["news_sentiment"].isna().all()

    ready = assemble("btc-trend-24-72-demo", SNAPSHOT_READY, n_estimators=30, n_boot=8)
    assert ready.result.provenance["prices"] == "binance_spot_btcusdt_1h"
    assert ready.result.provenance["news"] == "omitted"
    assert ready.result.provenance["strategies"] == "demo_generator"
    assert ready.result.provenance["costs"].startswith("assumed_")
    assert ready.result.dataset_hashes["market"] == manifest["market_hash"]
    assert ready.lgbm.fitted_on == "train"
    assert ready.lgbm.calibrated_on == "train_tail"
    assert ready.result.coverage["news_sentiment"] == 0.0
    assert ready.result.coverage["fear_greed"] > 0.99
    with pytest.raises(PermissionError):
        ready.runner.evaluate({"policy_id": "cash", "family": "cash"}, "test")
    assert ready.result.decision is not None
    assert ready.result.decision.verdict in {
        "KEEP",
        "MODIFY",
        "COMBINE",
        "RESTRICT",
        "MONITOR",
        "KILL",
        "INCONCLUSIVE",
    }
    assert ready.result.paper_plan is not None
    assert ready.result.paper_plan.completed is False
    assert ready.result.paper_plan.approved is False
    assert ready.result.paper_plan.horizon_days == 14


def test_five_minute_series_is_six_months_and_not_the_sealed_snapshot():
    manifest = json.loads(FIVE_MIN_MANIFEST_PATH.read_text())
    bars = read_binance_klines(FIVE_MIN_PATH)
    assert manifest["id"] == "binance-spot-btcusdt-5m-202605-202611"
    assert manifest["id"] != SNAPSHOT_READY
    assert manifest["interval"] == "5m"
    assert manifest["n_bars"] == 52992
    assert manifest["n_gaps_over_5m"] == 0
    assert hash_ohlcv(bars) == manifest["market_hash"]
    assert bars["open_time"].iloc[0] == pd.Timestamp("2026-05-08", tz="UTC")
    assert bars["open_time"].iloc[-1] == pd.Timestamp("2026-11-07 23:55", tz="UTC")
    spacing = bars["open_time"].diff().dropna()
    assert (spacing == pd.Timedelta(minutes=5)).all()


def test_cost_rows_match_the_compounded_baseline_and_do_not_double_count(bundle):
    for split in ("train", "validation", "test"):
        cost = next(row for row in bundle.result.costs if row.split == split)
        always = next(row for row in bundle.result.baselines if row.split == split and row.policy == "always_on")
        assert cost.net_return == pytest.approx(always.metrics.net_return)
        assert cost.gross_return - cost.fees - cost.slippage - cost.switching == pytest.approx(cost.net_return)
        assert cost.switching == pytest.approx(0.0)
        assert cost.fees > 0 and cost.slippage > 0
        assert cost.fees / cost.slippage == pytest.approx(10.0)


def test_switching_is_only_the_turnover_a_gate_adds():
    n = 8
    frame = pd.DataFrame(
        {
            "target_position": np.ones(n),
            "ret_next": np.full(n, 0.01),
            "split": ["train"] * n,
        }
    )
    held = simulate(frame, pd.Series(1.0, index=frame.index))
    flipped = simulate(frame, pd.Series([1.0, 0.0] * (n // 2)))
    held_cost = _cost_row(frame, held, "train")
    flipped_cost = _cost_row(frame, flipped, "train")
    assert held_cost.switching == pytest.approx(0.0)
    assert held_cost.net_return == pytest.approx(_compound(held["net"].to_numpy(dtype=float)))
    assert held_cost.gross_return - held_cost.fees - held_cost.slippage - held_cost.switching == pytest.approx(held_cost.net_return)
    assert flipped_cost.switching > 0
    assert flipped_cost.gross_return - flipped_cost.fees - flipped_cost.slippage - flipped_cost.switching == pytest.approx(
        flipped_cost.net_return
    )


def test_renamed_policy_keeps_the_same_interval(bundle):
    assert N_BOOT == 2000
    runner = bundle.runner
    original = dict(runner.rule_spec)
    renamed = dict(original)
    renamed["policy_id"] = original["policy_id"] + "-renamed"
    first = runner.evaluate(original, "validation")
    second = runner.evaluate(renamed, "validation")
    assert first.ci_delta[0] != first.ci_delta[1]
    assert first.ci_delta == second.ci_delta
    assert first.metrics.ci_net_return == second.metrics.ci_net_return
    # Same decisions, different body: the interval follows the body.
    changed = dict(original)
    changed["thresholds_selected_on"] = "renamed-only"
    third = runner.evaluate(changed, "validation")
    assert third.metrics.net_return == pytest.approx(first.metrics.net_return)
    assert third.ci_delta != first.ci_delta


def test_allocation_mix_counts_in_position_bars_only(bundle):
    spec = bundle.runner.rule_spec
    evaluation = bundle.runner.evaluate(spec, "validation")
    part = bundle.frame[bundle.frame["split"] == "validation"]
    in_position = part["target_position"].abs() > 1e-12
    assert evaluation.n_decisions == len(part)
    assert evaluation.n_in_position == int(in_position.sum())
    assert evaluation.n_in_position < evaluation.n_decisions
    chosen = allocation(spec, part, lgbm=bundle.lgbm).to_numpy(dtype=float)[in_position.to_numpy()]
    for level in (0.0, 0.5, 1.0):
        expected = float(np.isclose(chosen, level).mean())
        assert evaluation.allocation_mix[str(level)] == pytest.approx(expected)
    assert sum(evaluation.allocation_mix.values()) == pytest.approx(1.0)


def test_lightgbm_spec_records_seed_and_a_stable_model_hash(bundle):
    first = _fit_lgbm(bundle.frame, seed=7, n_estimators=40)
    second = _fit_lgbm(bundle.frame, seed=7, n_estimators=40)
    other = _fit_lgbm(bundle.frame, seed=9, n_estimators=40)
    assert first.calibrated_on == "train_tail"
    assert first.spec()["seed"] == 7
    assert first.spec()["model_hash"] == second.spec()["model_hash"]
    assert first.spec()["model_hash"] != other.spec()["model_hash"]
    assert len(first.spec()["model_hash"]) == 16
    assert first.base_rate is not None
    assert first.low == pytest.approx(first.base_rate - BAND)
    assert first.high == pytest.approx(first.base_rate + BAND)
    assert first.spec()["thresholds"] == [first.low, first.high]
    assert first.spec()["band"] == BAND


def test_regime_filter_is_chosen_on_train_and_ignores_the_sealed_window(bundle):
    spec = bundle.runner.regime_spec
    assert spec["selected_on"] == "train"
    assert spec["family"] == "regime_gate"
    poisoned = bundle.frame.copy()
    poisoned.loc[poisoned["split"] == "test", "ret_next"] = -0.2
    poisoned.loc[poisoned["split"] == "validation", "momentum_24h"] += 5
    again = discover_regime_filter(
        poisoned,
        simulate(poisoned, pd.Series(1.0, index=poisoned.index)),
        seed=7,
        n_boot=30,
    )
    assert again["flat_buckets"] == spec["flat_buckets"]
    assert again["full_buckets"] == spec["full_buckets"]
    assert "sentiment_regime" in bundle.frame.columns
    assert "liquidity_regime" in bundle.frame.columns
    assert bundle.result.coverage["news_sentiment"] == 0.0


def test_regime_filter_goes_flat_where_the_train_interval_is_below_zero():
    n = 120
    regime = np.array(["high"] * 60 + ["low"] * 60)
    frame = pd.DataFrame(
        {
            "split": ["train"] * n,
            "vol_regime": regime,
            "target_position": np.ones(n),
        }
    )
    net = np.where(regime == "high", -0.01, 0.01)
    simulated = pd.DataFrame({"net": net, "q": np.ones(n), "dq_signed": np.zeros(n)})
    spec = discover_regime_filter(frame, simulated, seed=1, n_boot=20)
    assert {"axis": "vol_regime", "bucket": "high"} in spec["flat_buckets"]
    assert {"axis": "vol_regime", "bucket": "low"} in spec["full_buckets"]
    context = pd.DataFrame({"vol_regime": ["high", "low", "low"]})
    assert regime_gate_allocation(spec, context).tolist() == [0.0, 1.0, 1.0]


def test_paper_plan_champion_is_the_policy_the_verdict_chose():
    modify = Decision(verdict="MODIFY", policy_id="rule::regime_filter", reasons=["interval above zero"], evidence={})
    plan = build_paper_plan("exp", "strat", "v1", modify, "10 bps")
    assert plan.champion_policy_id == "rule::regime_filter"
    assert plan.challenger_policy_id == "always_on"
    kill = Decision(verdict="KILL", policy_id="cash", reasons=["below zero"], evidence={})
    killed = build_paper_plan("exp", "strat", "v1", kill, "10 bps")
    assert killed.champion_policy_id == "cash"
    assert killed.challenger_policy_id == "always_on"
    keep = Decision(verdict="KEEP", policy_id="always_on", reasons=["above zero"], evidence={})
    kept = build_paper_plan("exp", "strat", "v1", keep, "10 bps")
    assert kept.champion_policy_id == "always_on"


def test_fold_score_keeps_the_open_position_and_ignores_embargo_returns():
    n = 160
    frame = pd.DataFrame(
        {
            "decision_time": pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC"),
            "split": ["train"] * n,
            "target_position": np.ones(n),
            "ret_next": np.zeros(n),
            "momentum_24h": np.zeros(n),
            "realized_vol_7d": np.zeros(n),
        }
    )
    runner = GateRunner(frame, None, seed=1, n_boot=8, snapshot_id="x", thresholds={})  # type: ignore[arg-type]
    spec = {"policy_id": "always_on", "family": "always_on"}
    held = runner.evaluate_folds(spec)
    # Already in the market, so the fold does not pay a fresh entry. A slice restarted at
    # zero would charge one entry on the first scored bar.
    assert [item.fold for item in held] == [1, 2, 3]
    assert held[0].n_decisions == 40
    assert held[0].metrics.turnover == pytest.approx(0.0)
    assert held[0].metrics.net_return == pytest.approx(0.0)
    frame.loc[38:39, "ret_next"] = 0.5
    untouched = runner.evaluate_folds(spec)
    assert untouched[0].metrics.net_return == pytest.approx(0.0)
    frame.loc[40, "ret_next"] = 0.01
    moved = runner.evaluate_folds(spec)
    assert moved[0].metrics.net_return == pytest.approx(0.01)
    assert moved[0].n_decisions == 40


def test_feature_series_refuses_the_forward_label(bundle):
    with pytest.raises(PermissionError):
        bundle.runner.feature_series("ret_next", split="train")
    train_times = set(bundle.runner.feature_series("fear_greed", split="train"))
    valid = bundle.runner.feature_series("fear_greed", split="validation")
    assert valid
    assert set(valid).isdisjoint(train_times)


def test_evaluate_folds_stays_inside_train_and_matches_the_walk_forward_windows(bundle):
    spec = dict(bundle.runner.rule_spec)
    renamed = dict(spec)
    renamed["policy_id"] = spec["policy_id"] + "-renamed"
    first = bundle.runner.evaluate_folds(spec)
    second = bundle.runner.evaluate_folds(renamed)
    assert [item.fold for item in first] == [1, 2, 3]
    assert all(item.split == "train" for item in first)
    assert [item.ci_delta for item in first] == [item.ci_delta for item in second]
    assert bundle.runner.holdout_log == []
    by_fold = {item.fold: item for item in first}
    scored = [fold for fold in bundle.result.walk_forward if fold.delta_net_return_vs_always_on is not None]
    assert scored
    for fold in scored:
        assert by_fold[fold.fold].n_decisions == fold.n_score
    before = [item.metrics.net_return for item in first]
    poisoned = GateRunner(
        bundle.frame.copy(),
        bundle.lgbm,
        seed=bundle.runner.seed,
        n_boot=bundle.runner.n_boot,
        snapshot_id=bundle.runner.snapshot_id,
        thresholds=bundle.thresholds,
    )
    poisoned.frame.loc[poisoned.frame["split"] == "test", "ret_next"] = -0.2
    poisoned.frame.loc[poisoned.frame["split"] == "validation", "ret_next"] = 0.4
    after = poisoned.evaluate_folds(spec)
    assert [item.metrics.net_return for item in after] == pytest.approx(before)


def test_feature_series_is_the_train_column_and_refuses_the_holdout(bundle):
    series = bundle.runner.feature_series("fear_greed", split="train")
    train = bundle.frame[bundle.frame["split"] == "train"]
    assert len(series) == len(train)
    assert series[0][0] == train["decision_time"].iloc[0].to_pydatetime()
    assert series[0][1] == pytest.approx(float(train["fear_greed"].iloc[0]))
    with pytest.raises(PermissionError):
        bundle.runner.feature_series("fear_greed", split="test")
    with pytest.raises(KeyError):
        bundle.runner.feature_series("not_a_feature", split="train")


def test_simple_rule_goes_flat_when_the_condition_fails():
    train = pd.DataFrame({"momentum_24h": [0.1, -0.1], "realized_vol_7d": [0.01, 0.01]})
    spec = rule_gate_spec(train)
    assert spec["allocation_when_true"] == 1.0
    assert spec["allocation_when_false"] == 0.0
    context = pd.DataFrame(
        {
            "momentum_24h": [-0.2, 0.2, 0.2],
            "realized_vol_7d": [0.01, 0.01, 0.05],
        }
    )
    assert allocation(spec, context).tolist() == [0.0, 1.0, 0.0]


def _evaluation(policy: str, net: float, drawdown: float, exposure: float, ci_net, ci_delta, delta: float) -> GateEvaluation:
    metrics = Metrics(
        net_return=net,
        max_drawdown=drawdown,
        turnover=1.0,
        n_switches=4,
        exposure=exposure,
        ci_net_return=ci_net,
    )
    return GateEvaluation(
        policy_id=policy,
        split="test",
        metrics=metrics,
        always_on=metrics,
        delta_net_return_vs_always_on=delta,
        ci_delta=ci_delta,
        audit_id=f"audit_{policy}",
    )


def _panel(always, rule, model, cash=None) -> dict[str, GateEvaluation]:
    if cash is None:
        cash = _evaluation("cash", 0.0, 0.0, 0.0, (0.0, 0.0), (0.0, 0.0), 0.0)
    return {"always_on": always, "cash": cash, "simple_rule": rule, "lgbm_gate": model}


def test_arbiter_abstains_when_the_interval_contains_zero():
    always = _evaluation("always_on", -0.02, 0.12, 0.6, (-0.04, 0.03), (0.0, 0.0), 0.0)
    rule = _evaluation("simple_rule", 0.01, 0.10, 0.3, (-0.02, 0.04), (-0.01, 0.03), 0.03)
    model = _evaluation("lgbm_gate", -0.01, 0.11, 0.4, (-0.05, 0.02), (-0.04, 0.02), 0.01)
    decision = decide(_panel(always, rule, model), n_test=MIN_TEST_DECISIONS)
    assert decision.verdict == "INCONCLUSIVE"
    assert decision.risk_override is False


def test_arbiter_abstains_when_the_test_is_too_short():
    always = _evaluation("always_on", 0.2, 0.05, 0.6, (0.1, 0.3), (0.0, 0.0), 0.0)
    rule = _evaluation("simple_rule", 0.4, 0.05, 0.4, (0.2, 0.5), (0.05, 0.2), 0.2)
    model = _evaluation("lgbm_gate", 0.1, 0.05, 0.4, (0.0, 0.2), (-0.02, 0.04), -0.1)
    decision = decide(_panel(always, rule, model), n_test=MIN_TEST_DECISIONS - 1)
    assert decision.verdict == "INCONCLUSIVE"


def test_arbiter_activates_when_the_gate_interval_is_above_zero():
    always = _evaluation("always_on", 0.02, 0.10, 0.7, (-0.01, 0.05), (0.0, 0.0), 0.0)
    rule = _evaluation("simple_rule", 0.08, 0.11, 0.4, (0.02, 0.12), (0.01, 0.08), 0.06)
    model = _evaluation("lgbm_gate", 0.03, 0.10, 0.5, (-0.01, 0.06), (-0.02, 0.03), 0.01)
    decision = decide(_panel(always, rule, model), n_test=400)
    assert decision.verdict == "MODIFY"
    assert decision.policy_id == "simple_rule"


def test_drawdown_cap_blocks_an_otherwise_winning_gate():
    always = _evaluation("always_on", 0.02, 0.50, 0.7, (-0.01, 0.05), (0.0, 0.0), 0.0)
    rule = _evaluation("simple_rule", 0.10, DRAWDOWN_CAP + 0.05, 0.4, (0.04, 0.16), (0.02, 0.10), 0.08)
    model = _evaluation("lgbm_gate", 0.01, 0.20, 0.5, (-0.02, 0.04), (-0.03, 0.02), -0.01)
    decision = decide(_panel(always, rule, model), n_test=400)
    assert decision.verdict == "MONITOR"
    assert decision.risk_override is True


def test_arbiter_kills_when_always_on_is_reliably_below_zero_and_past_the_cap():
    always = _evaluation("always_on", -0.30, DRAWDOWN_CAP + 0.10, 0.8, (-0.40, -0.05), (0.0, 0.0), 0.0)
    rule = _evaluation("simple_rule", -0.10, 0.20, 0.3, (-0.20, 0.02), (-0.05, 0.20), 0.20)
    model = _evaluation("lgbm_gate", -0.12, 0.25, 0.4, (-0.22, 0.01), (-0.04, 0.15), 0.18)
    decision = decide(_panel(always, rule, model), n_test=400)
    assert decision.verdict == "KILL"
    assert decision.policy_id == "cash"
    assert decision.risk_override is True


def test_arbiter_reduces_when_full_size_breaks_the_drawdown_cap():
    always = _evaluation("always_on", -0.04, DRAWDOWN_CAP + 0.08, 0.8, (-0.10, 0.02), (0.0, 0.0), 0.0)
    rule = _evaluation("simple_rule", -0.01, 0.20, 0.3, (-0.06, 0.04), (-0.04, 0.08), 0.03)
    model = _evaluation("lgbm_gate", -0.02, 0.22, 0.5, (-0.08, 0.03), (-0.05, 0.06), 0.02)
    decision = decide(_panel(always, rule, model), n_test=400)
    assert decision.verdict == "RESTRICT"
    assert decision.policy_id == "simple_rule"
    assert decision.risk_override is True


def test_arbiter_keeps_a_strategy_whose_interval_is_above_zero():
    always = _evaluation("always_on", 0.15, 0.08, 0.6, (0.04, 0.22), (0.0, 0.0), 0.0)
    rule = _evaluation("simple_rule", 0.12, 0.09, 0.4, (0.01, 0.20), (-0.08, 0.04), -0.03)
    model = _evaluation("lgbm_gate", 0.10, 0.09, 0.5, (-0.01, 0.18), (-0.10, 0.02), -0.05)
    decision = decide(_panel(always, rule, model), n_test=400)
    assert decision.verdict == "KEEP"
    assert decision.policy_id == "always_on"


def test_agent_view_drops_sealed_test_numbers_and_keeps_the_window(bundle):
    view = agent_view(bundle.result)
    assert any(window.split == "test" for window in view.windows)
    assert view.decision is None and view.paper_plan is None
    assert all(row.split != "test" for row in view.baselines)
    assert all(row.split != "test" for row in view.per_regime)
    assert all(row.split != "test" for row in view.costs)
    assert all(point.split != "test" for point in view.equity)
    assert all(point.split != "test" for point in view.comparison_equity)
    assert any(point.split == "test" for point in bundle.result.comparison_equity)
    assert any(row.split == "test" for row in bundle.result.baselines)
    assert bundle.result.decision is not None
    verdict = bundle.result.decision.verdict
    assert any("deterministic arbiter" in note and verdict in note for note in bundle.result.notes)
    assert all("deterministic arbiter" not in note for note in view.notes)
    assert all(verdict not in note for note in view.notes)
    view_range = view.train_predictive_range
    full_range = bundle.result.train_predictive_range
    assert view_range is not None and full_range is not None
    assert view_range.low == full_range.low
    assert view_range.high == full_range.high
    assert view_range.horizon_bars == full_range.horizon_bars


def test_experiment_records_an_unstarted_paper_plan(bundle):
    decision = bundle.result.decision
    plan = bundle.result.paper_plan
    assert decision is not None and plan is not None
    assert decision.verdict != "COMBINE"
    assert plan.completed is False
    assert plan.approved is False
    assert plan.horizon_days == 14
    assert plan.status == "recorded_not_started"
    if decision.verdict == "KILL":
        assert plan.champion_policy_id == "cash"
        assert plan.challenger_policy_id == "always_on"
    elif decision.verdict in {"MODIFY", "RESTRICT", "COMBINE"}:
        assert plan.champion_policy_id == decision.policy_id
        assert plan.challenger_policy_id == "always_on"
    else:
        assert plan.champion_policy_id == "always_on"
    assert plan.frozen_at_experiment == bundle.result.experiment_id
    assert "not a result" in " ".join(plan.notes)
    assert plan.predictive_range_low is not None and plan.predictive_range_high is not None
    assert plan.predictive_range_low < plan.predictive_range_high
    assert plan.predictive_horizon_bars == 14 * 24
    stored = bundle.result.train_predictive_range
    assert stored is not None
    assert stored.low == plan.predictive_range_low
    assert stored.high == plan.predictive_range_high
    assert stored.horizon_bars == plan.predictive_horizon_bars
    poisoned = bundle.frame.copy()
    poisoned.loc[poisoned["split"] != "train", "ret_next"] = 0.25
    original = simulate(bundle.frame, pd.Series(1.0, index=bundle.frame.index))
    changed = simulate(poisoned, pd.Series(1.0, index=poisoned.index))
    train = bundle.frame["split"] == "train"
    assert np.allclose(original.loc[train, "net"], changed.loc[train, "net"])
    scored = [fold for fold in bundle.result.walk_forward if fold.delta_net_return_vs_always_on is not None]
    assert scored and all("sealed-test" in fold.note for fold in scored)
    train_end = next(window.end for window in bundle.result.windows if window.split == "train")
    assert all(fold.score_end <= train_end for fold in bundle.result.walk_forward)
    line = next(note for note in bundle.result.notes if "walk-forward" in note.lower() or "Walk-forward" in note or "Honest negative" in note)
    if all(fold.delta_net_return_vs_always_on < 0 for fold in scored):
        assert "Honest negative" in line
    assert "sealed-test policy" in line
    assert {check.scale for check in bundle.result.fee_checks} == {0.5, 1.0, 2.0}
    assert bundle.result.coverage["atr_14"] == 1.0
    assert bundle.result.coverage["momentum_7d"] == 1.0
    assert bundle.result.coverage["price_drawdown"] == 1.0
    rule = next(row for row in bundle.result.baselines if row.policy == "simple_rule" and row.split == "test")
    assert rule.metrics.cvar_05 is not None
    assert rule.metrics.avg_holding_bars is not None


def test_hourly_shadow_log_records_fourteen_days_after_approval():
    from kok_a.contracts import PaperPlan
    from kok_a.paper import open_shadow, record_shadow

    plan = open_shadow(
        PaperPlan(
            plan_id="paper_test",
            strategy_id="btc-trend-24-72-demo",
            strategy_version="trend-sma-24-72-v1",
            champion_policy_id="always_on",
            challenger_policy_id="cash",
            frozen_at_experiment="exp",
            cost_assumptions="10 bps fee + 1 bp slippage",
            predictive_range_low=-0.05,
            predictive_range_high=0.05,
            predictive_horizon_bars=14 * 24,
            notes=["not a result"],
        )
    )
    assert plan.status == "awaiting_bars" and plan.approved is True
    waiting = record_shadow(plan, pd.DataFrame())
    assert waiting.status == "awaiting_bars" and waiting.fills == []
    start = pd.Timestamp("2026-11-01", tz="UTC")
    rows = pd.DataFrame(
        {
            "decision_time": start + pd.to_timedelta(range(14 * 24), unit="h"),
            "champion_position": 1.0,
            "challenger_position": 0.0,
            "fill_open": 100.0,
            "champion_net": 0.0001,
            "challenger_net": 0.0,
            "fee": 0.0,
            "slippage": 0.0,
        }
    )
    sealed = plan.model_copy(update={"approved": False, "status": "recorded_not_started"})
    with pytest.raises(RuntimeError):
        record_shadow(sealed, rows)
    running = record_shadow(plan, rows.iloc[:10])
    assert running.status == "running" and running.completed is False and running.paper_conclusion is None
    done = record_shadow(plan, rows)
    assert done.status == "completed" and done.completed is True
    assert len(done.fills) == 14 * 24
    assert done.fills[0].decision_time == start.to_pydatetime()
    assert done.range_position == "inside" and done.paper_conclusion == "INCONCLUSIVE"
    crash = rows.copy()
    crash["champion_net"] = -0.01
    crashed = record_shadow(plan, crash)
    assert crashed.range_position == "below" and crashed.paper_conclusion == "MONITOR"
