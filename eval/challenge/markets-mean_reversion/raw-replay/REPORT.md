# Finance project test report

**Participant adapter**

Dataset: 300 cases; seed: 3801400848860824678; source: AgentVerse seeded generator v2.

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **300**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

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
| 9f85e11644601433af30 | £7,848.85 | -£1,427.95 | £7,390.73 | £9,276.80 | 15.39% |
| 7632433224bc21cf823d | £3,907.99 | £0.00 | £3,877.31 | £3,907.99 | 0.00% |
| bebbc1da81b49be90098 | £5,410.98 | £749.92 | £7,468.18 | £4,661.06 | 0.21% |
| 9ea7f25235215a3d89c2 | £6,007.01 | -£1,660.30 | £7,405.82 | £7,667.31 | 21.65% |
| 8fda9cb3dd3401dfb98b | £7,298.73 | £1,603.64 | £7,238.60 | £5,695.09 | 1.55% |
| 844a9ebbb7fb7dd9b0cd | £1,080.48 | £0.00 | £1,474.02 | £1,080.48 | 0.00% |
| d3d02f1a2f6b4c417964 | £1,129.19 | -£97.55 | £1,056.76 | £1,226.74 | 7.95% |
| b16cba02f90be9ab2d36 | £6,499.86 | £0.00 | £6,460.98 | £6,499.86 | 0.00% |
| bac3d63d3ecce1046f2e | £9,387.20 | -£121.22 | £5,612.24 | £9,508.42 | 27.41% |
| 30930d2f291f75998cc4 | £5,605.14 | -£3,002.28 | £8,096.00 | £8,607.42 | 34.88% |
| d520e4bb083a5032a5cc | £1,858.36 | -£209.77 | £1,303.65 | £2,068.13 | 10.14% |
| 2778e808a5065cd701dd | £9,817.03 | £0.00 | £14,578.00 | £9,817.03 | 0.00% |
| 3ac84488b0bd9ce4d020 | £3,824.65 | -£1,143.70 | £3,512.69 | £4,968.35 | 23.18% |
| ededcca6ad26e2163406 | £8,113.35 | £0.00 | £8,066.27 | £8,113.35 | 0.00% |
| 7438f4c80a7fc8d78308 | £5,973.84 | -£679.84 | £7,001.36 | £6,653.68 | 25.56% |
| e00cd83370ab7d06acea | £5,134.89 | -£835.14 | £5,717.87 | £5,970.03 | 13.98% |
| afbda47e607fdd649c37 | £1,324.25 | £0.00 | £1,726.90 | £1,324.25 | 0.00% |
| e96240c7c54dceb931bd | £7,908.05 | £0.00 | £9,201.04 | £7,908.05 | 0.00% |
| 9e9a8ca569c7c733dc13 | £4,336.82 | -£1,609.82 | £4,116.46 | £5,946.64 | 27.07% |
| 2cfdfad7b174c88ed41c | £5,831.87 | £0.00 | £5,795.85 | £5,831.87 | 0.00% |
| 0c39bae7fe9e053aaf35 | £3,051.49 | £219.79 | £3,153.14 | £2,831.70 | 3.11% |
| 03d1b328683942b72bf5 | £6,623.10 | -£833.42 | £7,050.98 | £7,456.52 | 11.17% |
| 5b9e992f1831b1da71db | £3,217.45 | £1.26 | £2,189.04 | £3,216.19 | 0.15% |
| f26e3d373d9b13d03ed4 | £7,441.48 | £0.00 | £12,746.08 | £7,441.48 | 0.00% |
| 202453db65811492829c | £4,535.54 | -£2,993.98 | £4,244.08 | £7,529.52 | 39.76% |
| 05d9d78b7227f4e0c38e | £7,467.85 | £0.00 | £7,406.01 | £7,467.85 | 0.00% |
| 5792a8fd21451dafa69d | £6,428.13 | -£2,805.58 | £8,092.72 | £9,233.71 | 30.38% |
| bfe72e218be8a1eac389 | £3,803.84 | -£623.96 | £4,075.02 | £4,427.80 | 14.09% |
| dae026dcdd19c907a934 | £7,995.27 | -£56.52 | £11,045.81 | £8,051.79 | 1.03% |

Showing 30 of 300 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 300 paths:** 158 wins, 142 losses, 0 ties vs buy-and-hold; beat cash on 48. Median excess 0.28% of capital; mean max drawdown 9.76%; sign-test p = 0.387.
**Not distinguishable from buy-and-hold on these paths; more paths or a better edge is needed.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Expected answers stayed with the evaluator; adapter requests contained inputs only. The local answer files remain visible to developers, so this practice run is not cheat-proof. Use `bench.py challenge` for a result you can claim.
