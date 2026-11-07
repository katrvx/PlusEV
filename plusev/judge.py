"""The frozen judge. Deterministic statistics; no LLM anywhere in this file.

X-ray:        where does a strategy make and lose money? (per-regime tests,
              stationary bootstrap, Benjamini-Hochberg, sealed holdout)
Kill or Keep: is a live drawdown normal for this strategy, is the edge still
              alive, and how many more trades until we know? (bootstrap drawdown
              percentile, betting e-processes with Ville's inequality)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from .regime import FEATURES

Q_FDR = 0.10          # Benjamini-Hochberg false discovery rate
N_BOOT = 2000
MIN_TRADES = 15       # fewer trades in a bucket -> "thin", never green/red
ALPHA = 0.10          # e-process threshold 1/ALPHA


# ---------------------------------------------------------------- bootstrap

def stationary_indices(n: int, rng: np.random.Generator, mean_block: float) -> np.ndarray:
    """Politis-Romano stationary bootstrap: random-length blocks, wrapping around.
    Trades are serially dependent (vol clustering, overlapping regimes), so an iid
    bootstrap would understate variance and over-admit."""
    p = 1.0 / mean_block
    idx = np.empty(n, dtype=int)
    idx[0] = rng.integers(n)
    for i in range(1, n):
        idx[i] = rng.integers(n) if rng.random() < p else (idx[i - 1] + 1) % n
    return idx


def _mean_block(n: int) -> float:
    return max(1.0, n ** (1 / 3))


# ---------------------------------------------------------------- X-ray

def default_hypotheses() -> list[dict]:
    """The always-registered panel: every feature x bucket. Agents may add more via
    the ledger; the judge only ever tests registered hypotheses and reports the count."""
    return [{"feature": f, "bucket": b, "source": "default_panel"} for f, bs in FEATURES.items() for b in bs]


def _bucket_test(r: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> dict:
    """In-bucket minus out-of-bucket mean net return, with a stationary-bootstrap
    two-sided p-value and 90% CI."""
    n_in, n_out = int(mask.sum()), int((~mask).sum())
    if n_in < 2 or n_out < 2:
        return {"n_in": n_in, "effect": 0.0, "p": 1.0, "ci": [0.0, 0.0]}
    observed = r[mask].mean() - r[~mask].mean()
    diffs = np.empty(N_BOOT)
    mb = _mean_block(len(r))
    for b in range(N_BOOT):
        i = stationary_indices(len(r), rng, mb)
        rb, mbk = r[i], mask[i]
        if mbk.sum() < 1 or (~mbk).sum() < 1:
            diffs[b] = 0.0
            continue
        diffs[b] = rb[mbk].mean() - rb[~mbk].mean()
    centred = diffs - diffs.mean()
    p = float((np.abs(centred) >= abs(observed)).mean())
    lo, hi = np.quantile(diffs, [0.05, 0.95])
    return {"n_in": n_in, "effect": float(observed), "p": max(p, 1 / N_BOOT), "ci": [float(lo), float(hi)]}


def benjamini_hochberg(pvals: list[float], q: float = Q_FDR) -> list[bool]:
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    cutoff = 0
    for rank, i in enumerate(order, start=1):
        if pvals[i] <= q * rank / m:
            cutoff = rank
    keep = set(order[:cutoff])
    return [i in keep for i in range(m)]


def _arrays(trades: list[dict], feature: str):
    usable = [t for t in trades if t["regime"] is not None]
    r = np.array([t["net_return"] for t in usable])
    labels = np.array([t["regime"][feature] for t in usable])
    return r, labels


def xray(strategy: str, train: list[dict], holdout: list[dict], hypotheses: list[dict] | None = None,
         seed: int = 7, trained_on: str = "") -> dict:
    """Training-window tests -> BH correction -> confirmation on the sealed holdout."""
    rng = np.random.default_rng(seed)
    hyps = hypotheses or default_hypotheses()
    results = []
    for h in hyps:
        r, labels = _arrays(train, h["feature"])
        res = _bucket_test(r, labels == h["bucket"], rng)
        results.append({**h, **res})
    survived = benjamini_hochberg([x["p"] for x in results])

    buckets = []
    for x, ok in zip(results, survived):
        status = "thin" if x["n_in"] < MIN_TRADES else "neutral"
        confirmed = False
        hold = None
        if ok and status != "thin":
            r_h, l_h = _arrays(holdout, x["feature"])
            hold = _bucket_test(r_h, l_h == x["bucket"], rng)
            same_sign = np.sign(hold["effect"]) == np.sign(x["effect"]) != 0
            excludes_zero = hold["ci"][0] > 0 if x["effect"] > 0 else hold["ci"][1] < 0
            confirmed = bool(same_sign and excludes_zero and hold["n_in"] >= MIN_TRADES // 2)
            if confirmed:
                status = "green" if x["effect"] > 0 else "red"
        buckets.append({
            "feature": x["feature"], "bucket": x["bucket"], "source": x["source"],
            "n_train": x["n_in"], "effect_train": x["effect"], "ci_train": x["ci"], "p_train": x["p"],
            "survived_bh": bool(ok),
            "n_holdout": None if hold is None else hold["n_in"],
            "effect_holdout": None if hold is None else hold["effect"],
            "ci_holdout": None if hold is None else hold["ci"],
            "status": status,
        })

    r_all = np.array([t["net_return"] for t in train])
    return {
        "strategy": strategy,
        "trained_on": trained_on,
        "n_train_trades": len(train),
        "n_holdout_trades": len(holdout),
        "mean_net_return_train": float(r_all.mean()) if len(r_all) else 0.0,
        "hypotheses_proposed": len(hyps),
        "survived_training": int(sum(survived)),
        "confirmed_holdout": sum(b["status"] in ("green", "red") for b in buckets),
        "fdr_q": Q_FDR,
        "buckets": buckets,
    }


def save_envelope(env: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(env, indent=2))


# ---------------------------------------------------------------- e-processes

class BettingEProcess:
    """Test H0: E[y] <= 0 for y in [-1, 1] by betting (Waudby-Smith & Ramdas).

    Wealth W_t = W_{t-1} * (1 + lam_t * y_t), lam_t chosen from past data only
    (aGRAPA-style). Under H0 wealth is a nonnegative supermartingale, so by
    Ville's inequality P(sup_t W_t >= 1/alpha) <= alpha: the trader may look after
    every trade and the error guarantee still holds."""

    def __init__(self, max_bet: float = 0.5):
        self.wealth, self.n, self.s1, self.s2 = 1.0, 0, 0.0, 0.0
        self.max_bet = max_bet
        self.path = [1.0]

    def bet(self) -> float:
        if self.n < 2:
            return 0.1
        m = self.s1 / self.n
        v = self.s2 / self.n - m * m
        return float(min(self.max_bet, max(0.0, m / (v + m * m + 1e-12))))

    def update(self, y: float) -> float:
        y = max(-1.0, min(1.0, y))
        self.wealth *= 1 + self.bet() * y
        self.n += 1
        self.s1 += y
        self.s2 += y * y
        self.path.append(self.wealth)
        return self.wealth


def _scale(r: np.ndarray) -> float:
    return float(max(1e-9, 3 * np.std(r))) if len(r) > 1 else 1.0


def kill_or_keep(backtest: list[dict], live: list[dict], seed: int = 11, n_paths: int = 3000) -> dict:
    """Verdict for a live trade stream against its own backtest."""
    rng = np.random.default_rng(seed)
    rb = np.array([t["net_return"] for t in backtest])
    rl = np.array([t["net_return"] for t in live])
    mu_b, scale = float(rb.mean()), _scale(rb)
    n = len(rl)

    # 1. is this drawdown normal? bootstrap equity paths of the same length from the backtest
    def max_dd(rets: np.ndarray) -> float:
        eq = np.cumprod(1 + rets)
        eq = np.concatenate([[1.0], eq])
        return float(np.max(1 - eq / np.maximum.accumulate(eq)))

    live_dd = max_dd(rl) if n else 0.0
    mb = _mean_block(len(rb))
    sims = np.array([max_dd(rb[stationary_indices(len(rb), rng, mb)[:max(n, 1)]]) for _ in range(n_paths)])
    dd_pct = float((sims < live_dd).mean() * 100)

    # 2. edge alive? (H0: mean <= 0)   3. edge decayed? (H0: mean >= backtest mean)
    alive, decay = BettingEProcess(), BettingEProcess()
    for x in rl:
        alive.update(x / scale)
        decay.update((mu_b - x) / scale)

    # 4. trades until a decision: project forward assuming the future looks like the backtest
    def project() -> int:
        a = BettingEProcess()
        a.wealth, a.n, a.s1, a.s2 = alive.wealth, alive.n, alive.s1, alive.s2
        d = BettingEProcess()
        d.wealth, d.n, d.s1, d.s2 = decay.wealth, decay.n, decay.s1, decay.s2
        for k in range(1, 400):
            x = rb[rng.integers(len(rb))]
            if a.update(x / scale) >= 1 / ALPHA or d.update((mu_b - x) / scale) >= 1 / ALPHA:
                return k
        return 400

    proj = np.array([project() for _ in range(300)])

    if decay.wealth >= 1 / ALPHA:
        rec, why = "stop", "edge has decayed below the backtest at the 10% level (anytime-valid)"
    elif dd_pct > 99:
        rec, why = "pause", "drawdown is outside 99% of what the backtest implies"
    elif alive.wealth >= 1 / ALPHA:
        rec, why = "keep", "live edge confirmed above zero at the 10% level (anytime-valid)"
    elif dd_pct > 90:
        rec, why = "reduce", "drawdown unusual (above 90th percentile) but no decay detected yet"
    else:
        rec, why = "keep", "within what the backtest implies; not enough trades to decide yet"

    return {
        "n_live_trades": n,
        "live_mean_return": float(rl.mean()) if n else 0.0,
        "backtest_mean_return": mu_b,
        "live_drawdown": live_dd,
        "drawdown_percentile": dd_pct,
        "e_value_alive": alive.wealth,
        "e_value_decay": decay.wealth,
        "e_alive_path": alive.path,
        "e_decay_path": decay.path,
        "trades_to_decision": {"p10": int(np.quantile(proj, .1)), "median": int(np.median(proj)), "p90": int(np.quantile(proj, .9))},
        "recommendation": rec,
        "reason": why,
        "note": "trades_to_decision is a projection assuming future trades resemble the backtest",
    }
