# Finance project test report

**CHALLENGE (self-serve): hidden markets cases**

Dataset: 300 cases; seed: None; source: AgentVerse seeded generator v2 (hidden challenge).

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **300**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `351b6261d83ba998bd20238388aaa0490b0fe3064ec10b8b495b5d13b9dc51fc`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `2327e4591dc15d00900a5a8df2c0c39a972e3e92`, uncommitted changes: 3
- Provenance review: **4 item(s) need a human look:**
  - `.claude/worktrees/agent-afb2b6510fdfbe4e7/A/kok_a/binance.py`: downloads Binance history; fine for features, but check it is not used to look up hidden historical paths
  - `.claude/worktrees/agent-afb2b6510fdfbe4e7/A/kok_a/snapshot.py`: downloads Binance history; fine for features, but check it is not used to look up hidden historical paths
  - `A/kok_a/binance.py`: downloads Binance history; fine for features, but check it is not used to look up hidden historical paths
  - `A/kok_a/snapshot.py`: downloads Binance history; fine for features, but check it is not used to look up hidden historical paths

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
| 2728c7e9164bcbda7e9f | £8,624.89 | £0.00 | £10,062.47 | £8,624.89 | 0.00% |
| d1ac5a4d93884c7cdcf4 | £9,404.01 | £0.00 | £6,819.25 | £9,404.01 | 0.00% |
| ff8599a7dff6423c4518 | £1,915.63 | £0.00 | £1,901.51 | £1,915.63 | 0.00% |
| 02a4faa208e3a2dcc421 | £8,134.33 | £0.00 | £10,496.25 | £8,134.33 | 0.00% |
| f1f3500e7960e2fba09b | £2,547.40 | £0.00 | £2,510.88 | £2,547.40 | 0.00% |
| c94aed14e5c993356992 | £8,795.76 | £0.00 | £10,908.86 | £8,795.76 | 0.00% |
| f2809cb3eaeefbfc9d01 | £3,341.80 | £0.00 | £3,903.13 | £3,341.80 | 0.00% |
| 58c2b02927b4d3fda17b | £5,740.38 | -£838.11 | £3,755.99 | £6,578.49 | 12.74% |
| 9cda5ae8954b3be05386 | £1,059.73 | £0.00 | £1,051.23 | £1,059.73 | 0.00% |
| cb32b5fb91232734c8b0 | £7,091.57 | £1,011.64 | £4,259.26 | £6,079.93 | 6.85% |
| 6b591d700021cc815ab6 | £6,039.97 | £0.00 | £5,939.84 | £6,039.97 | 0.00% |
| 6c8d9139a77a9b4ae6a4 | £4,518.17 | -£60.72 | £3,148.49 | £4,578.89 | 1.42% |
| 0fc30d2efd6918f9f9fc | £4,192.93 | £0.00 | £5,556.55 | £4,192.93 | 0.00% |
| 14340d5a0ff676c4d2ab | £3,627.16 | -£252.91 | £2,476.08 | £3,880.07 | 6.61% |
| 82b0679c5994aa70fbc6 | £4,494.66 | £0.00 | £4,477.58 | £4,494.66 | 0.00% |
| e8c2b6cd9752aaa8f337 | £1,341.98 | £0.00 | £1,951.66 | £1,341.98 | 0.00% |
| 09ade26bd3dda397443f | £5,862.91 | £0.00 | £5,619.42 | £5,862.91 | 0.00% |
| 0c8652f5fd59570ac996 | £3,962.33 | £0.00 | £5,245.25 | £3,962.33 | 0.00% |
| 24334b2903a6a4585d7a | £5,089.56 | £0.00 | £6,251.00 | £5,089.56 | 0.00% |
| 885a3fb740677b13f7f9 | £6,172.89 | £0.00 | £5,560.28 | £6,172.89 | 0.00% |
| 57a9a26122f241e06117 | £3,273.06 | £0.00 | £3,260.60 | £3,273.06 | 0.00% |
| d1f912b89843ec7499b4 | £9,030.96 | £0.00 | £7,135.54 | £9,030.96 | 0.00% |
| c0e2bb6904ac3a8cc543 | £4,345.36 | -£651.70 | £4,515.69 | £4,997.06 | 13.04% |
| a1d7d03b9bd177944750 | £2,268.36 | £0.00 | £2,885.56 | £2,268.36 | 0.00% |
| 0e0736369178b68a1260 | £6,815.88 | £0.00 | £7,439.78 | £6,815.88 | 0.00% |
| 5cb99869ba24e5631a40 | £9,144.87 | -£245.62 | £6,486.07 | £9,390.49 | 2.61% |
| 047b6892bbe1a666641d | £3,158.86 | £0.00 | £3,146.70 | £3,158.86 | 0.00% |
| a2e36a42a2152b1805dd | £8,685.23 | £22.57 | £2,689.15 | £8,662.66 | 9.08% |
| d70c896666f80a34078e | £6,297.94 | £0.00 | £6,033.26 | £6,297.94 | 0.00% |
| ffbde202b1f2ed3b9f19 | £2,119.77 | -£23.96 | £1,524.47 | £2,143.73 | 1.11% |

Showing 30 of 300 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 300 paths:** 189 wins, 111 losses, 0 ties vs buy-and-hold; beat cash on 8. Median excess 0.71% of capital; mean max drawdown 1.55%; sign-test p = 0.000.
**Beat buy-and-hold more often than chance would explain on these paths.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
