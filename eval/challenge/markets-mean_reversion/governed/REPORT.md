# Finance project test report

**CHALLENGE (self-serve): hidden markets cases**

Dataset: 300 cases; seed: None; source: AgentVerse seeded generator v2 (hidden challenge).

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **300**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `eb9cebc007bc5747f337c61b725f771bdcf09cf8050d5a8adb4c57c9db9531b1`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `1cec3c7a099f072c197dd36d57dc2bdf83158279`, uncommitted changes: 1
- Provenance review: none flagged.

## Coverage

| Task / scenario family | Pass | Fail | Error | Simulated |
| --- | ---: | ---: | ---: | ---: |
| markets / falling | 0 | 0 | 0 | 50 |
| markets / flat | 0 | 0 | 0 | 50 |
| markets / jump | 0 | 0 | 0 | 50 |
| markets / regime_change | 0 | 0 | 0 | 50 |
| markets / rising | 0 | 0 | 0 | 50 |
| markets / volatile | 0 | 0 | 0 | 50 |

## Strategy results after costs

| Case | Final cash | Profit / loss | Buy-and-hold final | Cash baseline | Max drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| c7cb37129033e92dcb5d | £6,675.52 | £0.00 | £11,241.35 | £6,675.52 | 0.00% |
| 9f85e11644601433af30 | £9,218.96 | -£57.84 | £7,390.73 | £9,276.80 | 0.62% |
| 7632433224bc21cf823d | £3,907.99 | £0.00 | £3,877.31 | £3,907.99 | 0.00% |
| bebbc1da81b49be90098 | £4,661.06 | £0.00 | £7,468.18 | £4,661.06 | 0.00% |
| 9ea7f25235215a3d89c2 | £7,667.31 | £0.00 | £7,405.82 | £7,667.31 | 0.00% |
| 8fda9cb3dd3401dfb98b | £5,645.61 | -£49.48 | £7,238.60 | £5,695.09 | 0.86% |
| 844a9ebbb7fb7dd9b0cd | £1,080.48 | £0.00 | £1,474.02 | £1,080.48 | 0.00% |
| d3d02f1a2f6b4c417964 | £1,223.57 | -£3.17 | £1,056.76 | £1,226.74 | 0.25% |
| b16cba02f90be9ab2d36 | £6,499.86 | £0.00 | £6,460.98 | £6,499.86 | 0.00% |
| bac3d63d3ecce1046f2e | £9,398.48 | -£109.94 | £5,612.24 | £9,508.42 | 1.15% |
| 30930d2f291f75998cc4 | £8,607.42 | £0.00 | £8,096.00 | £8,607.42 | 0.00% |
| d520e4bb083a5032a5cc | £2,068.13 | £0.00 | £1,303.65 | £2,068.13 | 0.00% |
| 2778e808a5065cd701dd | £9,817.03 | £0.00 | £14,578.00 | £9,817.03 | 0.00% |
| 3ac84488b0bd9ce4d020 | £4,973.85 | £5.50 | £3,512.69 | £4,968.35 | 0.10% |
| ededcca6ad26e2163406 | £8,113.35 | £0.00 | £8,066.27 | £8,113.35 | 0.00% |
| 7438f4c80a7fc8d78308 | £6,653.68 | £0.00 | £7,001.36 | £6,653.68 | 0.00% |
| e00cd83370ab7d06acea | £5,958.13 | -£11.90 | £5,717.87 | £5,970.03 | 0.19% |
| afbda47e607fdd649c37 | £1,324.25 | £0.00 | £1,726.90 | £1,324.25 | 0.00% |
| e96240c7c54dceb931bd | £7,908.05 | £0.00 | £9,201.04 | £7,908.05 | 0.00% |
| 9e9a8ca569c7c733dc13 | £5,847.70 | -£98.94 | £4,116.46 | £5,946.64 | 1.66% |
| 2cfdfad7b174c88ed41c | £5,831.87 | £0.00 | £5,795.85 | £5,831.87 | 0.00% |
| 0c39bae7fe9e053aaf35 | £2,740.22 | -£91.48 | £3,153.14 | £2,831.70 | 3.23% |
| 03d1b328683942b72bf5 | £7,456.52 | £0.00 | £7,050.98 | £7,456.52 | 0.00% |
| 5b9e992f1831b1da71db | £3,217.45 | £1.26 | £2,189.04 | £3,216.19 | 0.15% |
| f26e3d373d9b13d03ed4 | £7,441.48 | £0.00 | £12,746.08 | £7,441.48 | 0.00% |
| 202453db65811492829c | £7,382.19 | -£147.33 | £4,244.08 | £7,529.52 | 1.95% |
| 05d9d78b7227f4e0c38e | £7,467.85 | £0.00 | £7,406.01 | £7,467.85 | 0.00% |
| 5792a8fd21451dafa69d | £9,233.71 | £0.00 | £8,092.72 | £9,233.71 | 0.00% |
| bfe72e218be8a1eac389 | £4,427.80 | £0.00 | £4,075.02 | £4,427.80 | 0.00% |
| dae026dcdd19c907a934 | £8,051.79 | £0.00 | £11,045.81 | £8,051.79 | 0.00% |

Showing 30 of 300 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 300 paths:** 193 wins, 107 losses, 0 ties vs buy-and-hold; beat cash on 9. Median excess 0.76% of capital; mean max drawdown 0.30%; sign-test p = 0.000.
**Beat buy-and-hold more often than chance would explain on these paths.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
