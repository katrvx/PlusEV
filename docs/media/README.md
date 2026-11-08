# Product screenshots

Captured from the production build of the local +EV web application at `http://127.0.0.1:3001` on 8 November 2026. These are actual UI captures, not generated mockups. Their wording and values were not retouched.

| File | Screen | Source state |
| --- | --- | --- |
| [homepage.png](homepage.png) | Homepage | `/`; the illustrated price path is explicitly conceptual. |
| [strategy-verdict.png](strategy-verdict.png) | Verdict and strategy health | `/?view=explore&strategy=btc-meanrev-48-demo&experiment=exp_a79497cf70ec` |
| [conditions.png](conditions.png) | Recorded market-condition findings | The same strategy and experiment, `view=explore&tab=conditions`. |
| [evidence.png](evidence.png) | Research, proposals, critic review and code checks | The same strategy and experiment, `view=explore&tab=evidence`. |
| [compare.png](compare.png) | Recorded comparison and exact checked filter | The same strategy and experiment, `view=compare`, scrolled to the sealed-look metrics. |

The homepage uses a 1280 × 720 viewport; the four workspace images use 1440 × 1000. The workspace captures use the app's reduced-motion setting for a stable image. Each is a direct viewport screenshot. Local development and visual-check captures remain under Git-ignored `artifacts/`.

The original strategy's **KILL** and its agent gate's result have different scopes. The historical test was previously seen by the team; read the [research record](../RESEARCH_RECORD.md) and [main README](../../README.md) alongside the screenshots. Saved paper protocols do not imply live execution or completed observations.

To refresh: start the API and web app using the root README, open **Try an example**, verify the strategy identity, capture the matching pages, then update this date and source-state record. Do not use illustrative fixtures as measured evidence.
