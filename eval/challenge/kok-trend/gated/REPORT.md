# Finance project test report

**CHALLENGE (self-serve): hidden markets cases**

Dataset: 300 cases; seed: None; source: AgentVerse seeded generator v2 (hidden challenge).

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **300**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `62281edc8f87e8be04776ca6153873ca76da63ea84933a9860f40dbb69990bb6`
- Seed: fresh random; revealed in SEED-REVEAL.txt after this run
- Kit fingerprint: `5c90bf815848f4edd85bb2446e00382a24f003d936b3bad72f297a3b7885dad9` (compare with the organisers' published value)
- Project commit: `2327e4591dc15d00900a5a8df2c0c39a972e3e92`, uncommitted changes: 4
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
| 8d44d8111b7afc10d9dd | £2,957.44 | £0.00 | £3,981.52 | £2,957.44 | 0.00% |
| 9597803c8587949e9c09 | £2,314.21 | £0.00 | £1,858.77 | £2,314.21 | 0.00% |
| 46b5a198d1ad372e2b17 | £6,083.85 | £0.00 | £6,048.81 | £6,083.85 | 0.00% |
| 7279e1c4ddba8b17fde1 | £8,618.22 | £0.00 | £8,670.64 | £8,618.22 | 0.00% |
| df5e22a50f83ef0d5296 | £7,166.12 | £0.00 | £7,387.86 | £7,166.12 | 0.00% |
| f7a06741e24a32799580 | £8,281.30 | £0.00 | £10,495.10 | £8,281.30 | 0.00% |
| 5d30cc39805435cbe88d | £6,657.51 | £0.00 | £9,727.35 | £6,657.51 | 0.00% |
| db6ec4dc683324b911d9 | £4,335.50 | £0.00 | £3,669.00 | £4,335.50 | 0.00% |
| 149caaad2686f7476603 | £7,039.78 | £0.00 | £7,007.74 | £7,039.78 | 0.00% |
| 9aaca21a51abcb783880 | £9,069.83 | £0.00 | £10,396.51 | £9,069.83 | 0.00% |
| 819f93efdd3d87604a9c | £8,736.62 | £0.00 | £8,201.62 | £8,736.62 | 0.00% |
| 9b5dd5c9785ea98a5f60 | £4,601.13 | £0.00 | £3,205.27 | £4,601.13 | 0.00% |
| 773436bcb9bd1efc45ca | £3,839.95 | £0.00 | £4,575.35 | £3,839.95 | 0.00% |
| 728fd309d1d716cb849e | £9,276.03 | £0.00 | £5,604.13 | £9,276.03 | 0.00% |
| d2f107efa1346804a932 | £7,681.61 | £0.00 | £7,651.71 | £7,681.61 | 0.00% |
| 232721365da0268c0ce1 | £7,915.62 | £0.00 | £7,218.14 | £7,915.62 | 0.00% |
| 94fd8483581fd27431ba | £7,455.10 | £0.00 | £7,381.92 | £7,455.10 | 0.00% |
| d696516a04525f0c6a68 | £8,283.01 | £0.00 | £5,609.71 | £8,283.01 | 0.00% |
| a934b3ae15cfb8c4ba6e | £1,116.76 | £0.00 | £1,387.60 | £1,116.76 | 0.00% |
| 35714c693d850638941c | £6,641.88 | £0.00 | £5,335.11 | £6,641.88 | 0.00% |
| 9fb8d7560ff1a6e0a35b | £8,141.13 | £0.00 | £8,121.59 | £8,141.13 | 0.00% |
| 64e9a074bc66b5111d2a | £4,549.76 | £0.00 | £2,842.26 | £4,549.76 | 0.00% |
| 805c71fcd1f1d4ea3bdc | £8,976.60 | £0.00 | £8,740.56 | £8,976.60 | 0.00% |
| f6bff64945ca3ae53bd0 | £8,546.17 | £0.00 | £6,145.55 | £8,546.17 | 0.00% |
| 3bc1c06410074ee6d4c6 | £8,225.35 | -£16.56 | £13,222.96 | £8,241.91 | 0.20% |
| 3afda0fafb0bdd2f8bcc | £9,795.51 | £0.00 | £7,332.87 | £9,795.51 | 0.00% |
| 170dc959369b69476354 | £9,015.18 | £0.00 | £9,006.98 | £9,015.18 | 0.00% |
| f8d87b1e8ac33419727e | £8,789.80 | £0.00 | £8,901.24 | £8,789.80 | 0.00% |
| 69eadff606e8ed0a9229 | £7,647.31 | £0.00 | £7,547.55 | £7,647.31 | 0.00% |
| e7f0fac11b813ef9f057 | £7,191.44 | £0.00 | £4,823.30 | £7,191.44 | 0.00% |

Showing 30 of 300 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 300 paths:** 198 wins, 102 losses, 0 ties vs buy-and-hold; beat cash on 4. Median excess 0.72% of capital; mean max drawdown 0.06%; sign-test p = 0.000.
**Beat buy-and-hold more often than chance would explain on these paths.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
