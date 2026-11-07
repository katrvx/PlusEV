# Finance project test report

**CHALLENGE (self-serve): hidden markets cases**

Dataset: 300 cases; seed: None; source: AgentVerse seeded generator v2 (hidden challenge).

Exact checks: **0 passed, 0 failed, 0 execution errors**.
Market simulations completed: **300**. Cases not run: **0**.

Only the configured adapter and defined checks were exercised. A baseline run tests the kit, not your submission.

## Challenge integrity

- Cases were generated in memory after the adapter was fixed; no input or answer file existed during the run.
- Seed commitment (published before scoring): `f99cd89d0696190c51c692d2630c3aea0d1c44fc21532abfd08c5cd92481612f`
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
| 235d0450155ba1effdf7 | £5,370.52 | £1,629.79 | £5,632.09 | £3,740.73 | 0.79% |
| 5f46a1a25f88d35c9a70 | £6,840.49 | £0.00 | £6,383.85 | £6,840.49 | 0.00% |
| 4a041cff7009bd5ff73b | £9,840.76 | £0.00 | £9,780.18 | £9,840.76 | 0.00% |
| 2d8b81fb588c58cb244e | £2,700.59 | -£1,235.35 | £3,399.06 | £3,935.94 | 45.46% |
| 715d11221a4f795a165f | £4,691.12 | -£230.56 | £4,862.34 | £4,921.68 | 4.68% |
| 90bb2856e96ca935f3d7 | £9,027.56 | -£326.96 | £6,195.21 | £9,354.52 | 3.49% |
| 6e8300319cdfe2ab22c9 | £8,877.59 | £1,848.60 | £8,956.49 | £7,028.99 | 0.19% |
| 453e5b8ed09e1bf534ce | £2,901.20 | £0.00 | £1,860.74 | £2,901.20 | 0.00% |
| 60f1c12577f6f9db1794 | £9,714.76 | £0.00 | £9,706.84 | £9,714.76 | 0.00% |
| 058362ad645b10f615b4 | £1,951.77 | -£206.35 | £2,080.06 | £2,158.12 | 12.95% |
| d6c8b1d3195c8b376b52 | £7,744.32 | £601.72 | £6,820.92 | £7,142.60 | 6.42% |
| b31b5727b3abf994b97f | £3,777.45 | £820.75 | £3,797.64 | £2,956.70 | 1.82% |
| 8fcd832b9035840b73fd | £11,853.79 | £2,331.37 | £12,564.48 | £9,522.42 | 0.40% |
| 71ea42c94c633fb68080 | £4,715.87 | £0.00 | £2,928.72 | £4,715.87 | 0.00% |
| 84bdafaf086aa40e3201 | £6,647.79 | £0.00 | £6,613.31 | £6,647.79 | 0.00% |
| 947a95078273824dab83 | £9,168.07 | £46.21 | £8,918.76 | £9,121.86 | 16.99% |
| 1557f84fe8774e42d26b | £4,082.68 | -£127.47 | £3,932.30 | £4,210.15 | 3.02% |
| b0bb21a458b971352e42 | £9,795.02 | -£128.16 | £6,980.66 | £9,923.18 | 2.40% |
| d7417c1c69f3baa37103 | £2,905.99 | £678.64 | £3,052.22 | £2,227.35 | 0.26% |
| e2d915fc8b6a3f67ec30 | £8,006.95 | £0.00 | £5,274.22 | £8,006.95 | 0.00% |
| 0a428b86ca976010f4ab | £6,778.15 | £0.00 | £6,729.47 | £6,778.15 | 0.00% |
| 2d8752f07100521d7db1 | £10,518.62 | £1,403.22 | £10,681.16 | £9,115.40 | 20.89% |
| 221c6f8abe9cbea72634 | £8,936.34 | £2,381.19 | £6,515.98 | £6,555.15 | 6.67% |
| b81c64b98cc8c6aa6e4e | £6,180.48 | -£454.75 | £8,343.87 | £6,635.23 | 8.52% |
| 174688d0ef88cad25b5f | £4,530.08 | £1,098.23 | £4,559.95 | £3,431.85 | 0.53% |
| e65311177a2040e1bef1 | £3,204.05 | £0.00 | £2,042.21 | £3,204.05 | 0.00% |
| d72863fb31e3dc26ac6f | £6,330.82 | £0.00 | £6,308.74 | £6,330.82 | 0.00% |
| bc27c7993c4d5936fc2d | £5,762.71 | £441.10 | £4,450.69 | £5,321.61 | 18.61% |
| 2d572f4d30231a1d5d13 | £9,858.69 | £2,476.20 | £7,041.09 | £7,382.49 | 4.14% |
| 09736abdb35aac8aff10 | £5,024.33 | -£2,272.51 | £5,016.12 | £7,296.84 | 31.32% |

Showing 30 of 300 paths; every result and trade is in case-results.jsonl.
Completing a simulation does not mean the strategy is good. Compare losses, costs, baselines and drawdown. These price paths do not model real market liquidity or predict returns.

**Across 300 paths:** 183 wins, 117 losses, 0 ties vs buy-and-hold; beat cash on 124. Median excess 0.59% of capital; mean max drawdown 5.80%; sign-test p = 0.000.
**Beat buy-and-hold more often than chance would explain on these paths.**

## Next action

Run your actual submission adapter if this was a baseline. Add project-specific checks, then rerun with a fresh seed. Anything outside these checks remains untested.

Hidden challenge run: no input or answer file existed while the adapter ran, and the kit's reference calculations were disabled for it.
