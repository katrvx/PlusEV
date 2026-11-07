# Keep or Kill — complete interface and motion direction

> Current implementation note: later user direction replaces the dark theme with white surfaces, navy text and an electric blue accent. Use neutral Inter typography, a bold result and one concise finding, thicker smooth curves, and minimal small-font detail. React Bits and Motion provide restrained, consistent interactions. See `CREATIVE_DIRECTION_IMPLEMENTATION.md` for the current design and unchanged integration contract; the original brief below remains reference material.

Copy this entire brief into the design or implementation agent. It defines the product flow, visual system, screens, chart behaviour, every reusable bubble, motion choreography, failure states and acceptance criteria. Treat the timings as deliberate design specifications, not research findings.

## 1. Your assignment

Act as the product designer, interaction designer and frontend engineer for **Keep or Kill**, a tool for semi-beginner systematic traders. Build a complete, coherent experience using the direction below. Make concrete decisions within this system rather than falling back to a component-library dashboard.

The user supplies an existing strategy's signals or target positions. The platform runs the historical backtest, explains the conditions surrounding performance, proposes an activation filter, independently tests that filter and supports an approved paper experiment. The platform does not require users to arrive with a completed backtest. Never use “Drop a backtest” as the input prompt.

Keep the base strategy unchanged. A proposed filter changes when or how much the strategy is active; it does not rewrite its signal-generation logic. Historical pattern discovery, testing on unseen history and prospective paper testing are distinct states with distinct labels.

For the MVP, accept supported timestamped signals or target-position files and example fixtures. Do not imply that arbitrary uploaded Python code is executable, or that a plain-English strategy description automatically becomes a runnable strategy. Only expose code integrations if they actually exist. Completed trades alone can support limited diagnosis; do not promise a faithful alternative backtest when required position information is missing.

The design should feel like a carefully made graphical research instrument: black space, precise orange marks, beautiful type and a few understandable actions. It should be easy to read in five seconds and rewarding to explore for five minutes.

## 2. The visual thesis

**One uninterrupted dark canvas. A graph as the main object. Short labels attached to what they explain. Motion that follows a meaningful event.**

The revised sidebar-free concepts are the visual reference. Preserve their open composition, orange curves, quiet top navigation and editorial headings. Correct their misleading upload wording and treat all pictured numbers as illustrative. Improve their usability: use sans-serif for controls, axes and explanations; reserve serif for the brand and major headings. Never reproduce an illustrative graph as a measured result.

The first visual impression must come from a chart's shape, a well-placed title and open space. It must not come from a wall of components.

Hard prohibitions:

- No left sidebar, vertical icon rail or persistent assistant column.
- No dashboard card grid, KPI tiles or rounded containers surrounding every graph.
- No generic “Welcome back” block, avatar cluster or decorative notification bell.
- No glassmorphism, neon glow, gradient blobs, animated background particles or 3D finance ornaments.
- No floating robot, chat bubble launcher, typing agent persona or theatrical chain-of-thought log.
- No huge pill-shaped buttons, rainbow status chips or default component-library appearance.
- No letter-by-letter heading reveals, slot-machine numbers, bouncing menus, parallax or scroll hijacking.
- No endlessly moving curves when no new data exists.
- No smoothing that erases losses, invents intermediate outcomes or makes financial results look more favourable.
- No fake progress percentages, fabricated confidence scores or permanent “AI is thinking” theatre.
- No celebratory confetti for a profitable result. This product must handle an unsuccessful strategy with equal visual care.

Compact temporary surfaces are permitted for a tooltip, menu, input editor, evidence detail or approval dialogue. These are tools that appear when needed, not the page's organising structure.

## 3. Exact visual tokens

Use these as the initial token set. Verify actual rendered contrast; adjust a token if necessary rather than weakening accessibility.

| Token | Value | Use |
|---|---|---|
| Canvas | `#0B0B0A` | Entire application background |
| Temporary surface | `#191714` | Opaque bubbles, menus, focused editors |
| Primary text | `#EEE9E1` | Headings, important values, active controls |
| Secondary text | `#B4AEA5` | Supporting labels and explanations |
| Quiet text | `#969088` | Dates and low-priority metadata; never disabled-looking essential copy |
| Accent | `#F47735` | Proposed filter curve, selected position, next action |
| Accent hover | `#FF9658` | Hover/focus emphasis, used briefly |
| Accent area | `rgba(244,119,53,0.10)` | Under a real plotted series, fading towards zero opacity |
| Hairline | `#302C27` | Nonessential separation |
| Essential boundary | `#7A736A` | Input affordances or controls that need a visible boundary |
| Original series | `#D6D0C7` | Original strategy, continuous line |
| Simple-rule series | `#A8A198` | Baseline filter, dashed line |
| Cash series | `#847D74` | Thin dotted zero-return reference |
| Focus | `#FFAA73` | Visible keyboard focus outline |

Orange does not mean “profit”. It means the proposed filter, a selection or an action. An orange series can lose money. Indicate positive/negative results with signed numbers and position around a labelled zero line. Indicate status with words and symbols, not colour alone.

No background texture is required. Do not add noise to compensate for weak layout. Any area fill belongs to data and must remain visually subordinate to the line.

### Type

Use **Instrument Serif Regular** for the wordmark and major headings, **Geist Sans** for interface text, and **Geist Mono** for aligned values, dates and numerical readouts. Self-host the chosen font assets when practical. Use system fallbacks immediately; loading a font must not leave text invisible.

| Role | Desktop | Mobile | Treatment |
|---|---|---|---|
| Wordmark | 30px / 34px | 26px / 30px | Serif; orange slash only |
| Screen heading | 48px / 52px | 34px / 38px | Serif; regular; maximum two lines |
| Upload invitation | 64px / 68px | 40px / 44px | Serif; only on the empty entry screen |
| Primary chart endpoint | 30px / 34px | 24px / 28px | Mono; tabular numerals |
| Body and main actions | 16px / 24px | 16px / 24px | Sans; regular or medium |
| Navigation and field labels | 14px / 20px | 14px / 20px | Sans; no all-caps navigation |
| Chart labels and metadata | 12px / 18px | 12px / 18px | Sans or mono; never smaller |
| Tiny section identifier | 12px / 18px | 12px / 18px | Optional uppercase; letter spacing 0.08em |

Use weight 400 normally and 500 for emphasis. No synthetic bold serif. Avoid italic explanatory paragraphs. Serif contributes character; charts and controls must remain immediately legible.

### Spacing and geometry

- Base spacing units: 4, 8, 12, 16, 24, 32, 48, 64 and 96px.
- At a 1440px viewport: content width 1328px; 56px outer margins.
- At 1024px: 32px outer margins. Below 768px: 20px, reducing to 16px at 360px.
- Main header: 80px high on desktop, at least 64px on mobile.
- Space from header to title block: 40px desktop, 28px mobile.
- Space between title block and dominant graphic: 40–56px desktop, 24px mobile.
- Typical desktop result chart: 380–480px tall, plus its labels. Small shared-axis tracks: 70–100px each.
- Do not fill every vertical pixel. Allow ordinary document scrolling when content needs it; do not force everything into a short fixed-height viewport.
- Page sections and charts have no corner radius because they have no surrounding box.
- Temporary surfaces: 8px radius. Input affordances: 4px radius where a boundary is needed. No giant rounded pill controls.
- Fine data strokes: original 1.5px, proposed filter 2px, baselines 1.25px. Essential lines retain sufficient contrast.

## 4. Navigation and screen structure

Use a small wordmark at top left and four text destinations at top right:

**Strategy · Explore · Compare · Observe**

“Strategy” contains add, check and test-setup states. “Explore” contains Overview, Conditions and Evidence. “Compare” contains independent validation and the subsequent paper-test review. “Observe” contains paper-run monitoring.

An active top-level destination has a 1.5px orange underline 7px beneath the label. No active-tab background. At most three quiet local tabs appear beneath the title when needed: **Overview · Conditions · Evidence**. Do not add another navigation tier.

Before a strategy exists, show the wordmark, the entry task and a small “Try an example” action. Do not confront a new user with a row of disabled tabs. Once a strategy is accepted, reveal the main navigation. Unavailable later stages provide a concise reason when selected, such as “Run a backtest first”; never silently ignore input.

Clicking the current strategy name opens a temporary strategy switcher. Render strategies as simple text rows: name, market, last run and short status. Maximum six visible rows before search/scroll is useful. An “Add strategy” row sits last. No thumbnail cards or permanent portfolio sidebar.

Use stable routes and an experiment identifier. Preserve the chosen strategy, selected date, chart window and evidence selection when moving between related views. Browser Back restores the prior view and focus target. Navigating away from a running job does not cancel it.

## 5. The motion language

Motion should feel light, controlled and slightly tactile. A bubble gently settles beside a point; a curve reveals an available result; an underline slides to the chosen view. The user should never wait for decoration before operating the page.

Define these motion tokens:

| Name | Value | Purpose |
|---|---|---|
| `instant` | 0–80ms | Pointer tracking and direct manipulation |
| `micro` | 120ms | Hover, short fade, press release |
| `bubble` | 180ms | Tooltip/popover entrance |
| `control` | 220ms | Underline and small layout change |
| `page` | 320ms | Content transition |
| `settle` | 420ms | Related plot layout transition |
| `trace` | 650ms maximum | First reveal of an available result curve |
| `ease-out` | `cubic-bezier(0.22,1,0.36,1)` | Most entrances and settling |
| `ease-in` | `cubic-bezier(0.4,0,1,1)` | Exits |
| `ease-balanced` | `cubic-bezier(0.4,0,0.2,1)` | Underlines and measured layout shifts |

The signature “pop” is opacity 0→1, scale 0.97→1, and a 4px movement away from the anchor, over 180ms using `ease-out`. It has no overshoot. Large surfaces never scale. Text is not blurred during entrance.

Only one major animation should demand attention at a time. Small hover feedback may coexist. Do not sequence five unrelated entrances just because the library supports staggering. The initial page becomes fully usable immediately and visually settled within 700ms of its data being available.

### Master animation registry

Every motion in the product must map to a row below. Do not invent additional loops or decorative transitions.

| ID | Trigger | Exact normal-motion behaviour | Reduced motion |
|---|---|---|---|
| M01 | Initial application render | Header opacity 0→1 over 160ms; title opacity 0→1 and y 8→0 over 260ms, starting 40ms after header; no replay on normal rerender | Immediate layout; optional 80ms fade |
| M02 | Top/local navigation changes | Existing underline moves/resizes to target over 220ms; outgoing content fades over 100ms; incoming content fades and moves y 8→0 over 240ms; preserve header | Underline and layout instant; 80ms content fade |
| M03 | Text action hover/focus | Colour to accent-hover over 120ms; arrow moves x 2px, y −2px over 160ms on hover only | Colour only; stationary arrow |
| M04 | Text action pressed | Underline opacity 1→0.65 over 60ms, returns over 120ms; do not scale the whole label | Instant state |
| M05 | File enters upload hit area | Existing upload underline expands to text width over 180ms; label becomes “Release to add”; accent tint changes over 120ms | Instant label and underline |
| M06 | File accepted | Upload instruction fades over 100ms; filename replaces it with y 6→0 over 220ms; no flying file icon | 80ms crossfade |
| M07 | File check finishes | Actual check mark appears over 140ms; affected line replaces its status with a 160ms fade; only animate changed rows | Instant status |
| M08 | Field editor/dropdown opens | Small surface opacity 0→1, y 4→0 over 180ms; no growth from zero height | 80ms fade |
| M09 | Field value saved | Value crossfades over 120ms, width reserved; short underline emphasis fades within 400ms | Instant value; optional 80ms fade |
| M10 | Job begins | Action becomes “Running…” in place over 120ms; finite top progress trace starts if backend reports work underway | Static status text |
| M11 | Indeterminate job remains active | A 28px orange segment traverses a 180px track over 1800ms; at most two cycles, then static track plus real elapsed time; repeat only on a new stage event | Static stage and elapsed time |
| M12 | Backend stage changes | Previous label fades over 100ms; new label enters y 4→0 over 180ms; genuine stage markers update over 160ms | Instant label |
| M13 | First completed chart appears | Axes fade over 120ms; all compared paths reveal together left-to-right with a clipping boundary over 650ms; values/labels are already readable; no zero-to-profit number counting | Entire chart appears immediately |
| M14 | Chart cursor moves | Guide and markers follow pointer in the next animation frame; no easing or trailing cursor; sampled values update together | Same direct interaction |
| M15 | Value bubble opens | After 120ms stable pointer dwell, signature pop over 180ms; keyboard/tap opens immediately without dwell | 80ms fade |
| M16 | Hovered point changes | Bubble stays mounted; content updates immediately, reserved numeric widths; location clamps to chart edges without a new pop | Same |
| M17 | Point/range is pinned | Marker gains a 1px outer ring over 120ms; a second ring expands radius 5→10px and fades once over 240ms | Static pinned ring |
| M18 | Insight/evidence bubble opens | Signature pop over 180ms; connector fades over 120ms; do not replay on data-label updates | 80ms fade; connector static |
| M19 | Any bubble closes | Opacity 1→0 over 100ms; scale 1→0.99 only for small bubbles; remove from interaction immediately when closing | Instant or 60ms fade |
| M20 | Local condition highlighted | Related intervals tint over 180ms; unrelated traces remain visible at reduced emphasis; date/selection guide stays aligned | Instant highlight |
| M21 | Same-data layout changes | With identical measure, timestamps and series identity, plot geometry may settle over 420ms; disable tooltips during this layout motion | Instant final geometry |
| M22 | Dataset, run, metric or axis meaning changes | Crossfade whole plot over 140ms, updating axes and values atomically; never morph one experiment into another | Instant replacement |
| M23 | Series toggled | Whole series and its labels fade over 140ms; retain comparable y-domain unless explicit fit command | Instant visibility |
| M24 | Range brushed | Selection follows drag immediately; release schedules actual computation; pending summary reads “Calculating…”; returned values fade over 120ms | Same direct interaction; instant values |
| M25 | Evidence source expanded inline | Reveal within normal flow over 220ms; content opacity follows after first 80ms; user focus remains stable | Immediate expansion |
| M26 | Policy review opens | Full-width review section enters y 10→0 and opacity 0→1 over 280ms; previous chart moves only if space changes | Immediate layout; 80ms fade |
| M27 | Paper run is confirmed by server | Action changes once to “Paper test started”; confirmation mark draws over 160ms; navigate after readable acknowledgement, maximum 400ms; no confetti | Instant acknowledgement then navigation |
| M28 | New paper observation arrives | Append only the new observed segment over 240ms; current point updates once; do not reanimate history or invent between-bar ticks | Append instantly |
| M29 | New factual notification | One small bottom message fades and moves y 6→0 over 180ms; ordinary confirmation remains at least 4s and pauses dismissal during hover/focus | 80ms fade |
| M30 | Validation error appears | Error text fades over 120ms beside the relevant field; no shaking, bouncing or flashing | Instant error |
| M31 | Data stale or disconnected | Status text replaces current status over 120ms; chart freezes at last actual observation; no animated movement implying activity | Instant status |
| M32 | First eligible research insight arrives | One small chart anchor becomes visible over 160ms; it does not auto-open a large explanation; selection opens M18 | Static anchor |
| M33 | Mobile navigation/menu opens | Opaque compact menu fades and moves y 4→0 over 180ms; no full-screen sweeping curtain | 80ms fade |
| M34 | Cancellation/pause acknowledged | Active progress stops immediately; status updates over 120ms after backend acknowledgement; retain last completed data | Instant update |
| M35 | Strategy switcher opens | Same M08 surface; selected row stays visible; choosing an item uses M22 for its plot, not a data morph | 80ms fade then atomic plot update |
| M36 | Keyboard focus changes | Focus outline appears immediately; never animate its travel between controls | Same |

Cancel superseded transitions rather than queueing them. If the user changes views twice quickly, the interface must settle on the latest selection. No animation may block cancellation, typing, scrolling or access to a completed result.

## 6. Bubble and temporary-surface system

“Bubble” means a small contextual explanation next to a relevant mark. It does not mean floating decorative circles. Keep the main chart visible.

Common construction:

- Opaque `Temporary surface` background; 1px subtle warm-grey edge; 8px corners.
- No blur, glass effect, heavy shadow or orange glow. An optional 6px low-opacity shadow only if essential to separate an overlay from the plot.
- Padding 12px; primary value 16px mono; support text 13–14px sans, 20px line height.
- Prefer a 1px connector ending in a 3px dot to a cartoon speech-tail triangle.
- Place 12px away from its anchor; clamp 12px inside the viewport. Choose the quadrant with least data occlusion.
- Keep at most one value bubble and one explicitly pinned insight visible. Opening a new pinned insight closes the old one. Menus and dialogues close transient chart bubbles.
- Tooltips contain text only. A bubble containing buttons or links is a labelled nonmodal popover/dialogue, with suitable focus behaviour; do not misuse `role=tooltip` for interactive content.
- Escape dismisses. Hover-triggered content can itself be hovered. Never hide it while the user is reading it or move it away from the pointer when entered.

| Type | Trigger | Contents and size | Persistence and dismissal |
|---|---|---|---|
| B01 Value readout | Chart hover/focus; tap pins | 180–240px wide; timestamp then one aligned row per visible series; signed value and unit; maximum five rows | Stays while trigger or bubble hovered/focused; tap/click pins; Escape/outside click closes |
| B02 Term explanation | Small underlined term or adjacent labelled help control | 180–260px; one plain-English sentence, maximum 28 words; e.g. “Largest fall is the biggest drop from a previous peak.” | Hover/focus is transient; tap toggles; no timed dismissal |
| B03 Finding | Select an orange evidence anchor | 240–320px; one-line finding, relevant date, sample count, uncertainty qualifier, “Open evidence” action | Explicitly pinned until closed or replaced |
| B04 Proposed rule | Select the condition label | 240–320px; readable rule, allocation outcome, “Proposal, not yet validated”; optional “Inspect definition” | Explicit click/tap only; close control and Escape |
| B05 Selected range | Release chart brush | 220–300px; exact start/end dates, actual selected sample count and descriptive result; “Selection only” label | Pinned until selection cleared; never replaces whole-test verdict |
| B06 Field editor | Click a setup value | Width 260–360px, max viewport minus 32px; labelled input, unit, hint, Save/Cancel; date picker can be wider | Click only; focus enters editor; Escape cancels; restored focus on close |
| B07 Run state | Select status text | Up to 280px; current stage, real elapsed time, last update and Cancel if supported | User-triggered; no imaginary remaining-time estimate |
| B08 Confirmation message | Save/export/start result acknowledged | 240–360px, one sentence; optional Undo only if real | At least 4s, hover/focus pauses timeout; actionable/error messages persist |
| B09 Error detail | Click concise inline error | Up to 320px; what failed, affected field/rows, one corrective action | Persists until dismissed or resolved; never covers its corrective control |
| B10 Source detail | Click dated evidence | Inline expansion preferred; when overlay is necessary, up to 400px with title, source, available-at time and external link | Click only; external link clearly identified; no hover-required source access |

No automatic bubble tour. On first use, one quiet inline hint may say “Select a point to see what changed.” Dismiss it permanently after the first successful selection.

## 7. Screen A — add a strategy

Purpose: make the first action unmistakable without asking for results the platform is supposed to calculate.

Visible copy:

- Main heading: **Test your strategy.**
- Main invitation: **Add your strategy.**
- One support line: **Upload its signals or positions. We’ll run the backtest.**
- Main action: **Choose file ↗**
- Secondary action: **Try an example**
- Quiet format line: **CSV or Parquet**

At desktop width, place the invitation around 38% of the available content height, with the action 24px below. The entire generous central region accepts a file drop, but it has no dashed rectangle. The underlined action provides the visible affordance. Keep a native accessible file chooser available. On touch, choosing a file is primary; do not imply drag-and-drop is required.

The lower 22% of the screen may show one restrained strategy-preview line, clearly labelled “Example”. This is a finite illustrated preview; it must not run a fake market simulation or promise an improved orange curve. Reveal it once using M13, then leave it still. Remove it on narrow screens if it competes with the action.

Add one term explanation B02 for “signals or positions”: “A timestamped record of what your strategy wanted to hold.” This should be accessible through the words, not an intimidating documentation block.

Drag enter uses M05; drag leave reverses the underline over 120ms. An accepted file uses M06. An unsupported file retains the invitation and displays “Use a CSV or Parquet file” below the action via M30. Never start a simulated analysis merely because a filename exists.

Choosing an example loads an explicitly named deterministic fixture and labels subsequent results “Example strategy”. It follows the same real validation and calculation flow.

## 8. Screen B — check the strategy data

Purpose: translate a technical schema check into a short, fixable conversation with the file.

Heading: **Check your strategy.** Filename beneath it in mono. Show at most four unboxed rows: **Time**, **Market**, **Position**, **Coverage**. Each row has the detected value and a short status such as “Found”, “Choose column”, or “Needs attention”. Rows are separated by spacing and a light hairline, not tiles.

If automatic mapping succeeds, show a small actual position trace across the imported dates, directly on the canvas. A position step series must use steps, not a beautifully smoothed line that invents intermediate positions. It is labelled “Strategy positions”, not “Performance”. No returns exist yet.

Column mapping is a B06 editor: source column, preview of three real values, destination meaning. Preserve original names in preview. Timezone and timestamp units are explicit when ambiguous; never silently guess a financially consequential interpretation.

Actual validation checks include ordering, duplicates, missing instrument, invalid numeric positions and the coverage necessary to run the supported simulator. Summarise the problem in plain English; detailed row numbers appear on request. Do not display a list of every internal validation rule.

Success action: **Set up backtest ↗**. Block only on issues that prevent a valid supported run. Example: “Target positions are missing. Add a position column to run this backtest.” If a trades-only file supports only diagnosis, clearly offer that narrower path; never present its output as an equivalent gated backtest.

Use M07 only as real checks complete. Errors use M30. Corrected mapping updates the trace atomically with M22. A short file check must not be artificially stretched to make the product look busy.

## 9. Screen C — set up the backtest

Purpose: obtain meaningful assumptions in a small readable form.

Heading: **Set up the test.** Support line: **Choose the period and trading costs.**

Use a narrow vertical arrangement of sentence-like field rows, not boxed settings cards:

- **Market** — detected instrument and supported venue.
- **Period** — start and end dates within available coverage.
- **Starting balance** — currency and amount.
- **Trading costs** — fee and slippage assumptions, with units.
- **Execution** — clear next-eligible-interval assumption.

Display the actual inputs needed by the selected supported venue. Funding/borrow fields appear when relevant; do not hide material costs under a vague “smart defaults” promise. Never invent venue-specific default costs. Suggested values need a stated source or an explicit “Example assumption” label.

Field values are underlined text controls opening B06. Prefer native semantic inputs and an accessible date picker. On mobile, use ordinary stacked inputs and native pickers if they are easier; visual minimalism must not make editing obscure.

A compact period strip beneath the date row shows available data and selected dates. It is one honest time scale. It updates directly during selection; there is no dynamic projected profit display.

A single **More assumptions** disclosure can contain annualisation, timezone and supported execution details. Keep important cost assumptions visible above it.

Main action: **Run backtest ↗**. Beneath it: **Your strategy stays unchanged.** A click validates, records the configuration and submits once. Disable duplicate submission while awaiting acknowledgement. Do not require an extra generic confirmation dialogue.

Changes after a completed run produce a new version when the user reruns. Preserve earlier results and identify the new assumptions. Never silently overwrite the experiment used for a previous recommendation.

## 10. Screen D — running and analysing

Purpose: communicate real progress and remain useful during a wait.

Heading: **Testing your strategy.** Show one current stage and a quiet completed-stage count. Supported stage labels:

1. **Checking the data**
2. **Preparing market history**
3. **Running the backtest**
4. **Finding market patterns**
5. **Preparing your results**

Map these to actual backend events. If some stages run in parallel, do not imply a false dependency; the display may use “Running backtest and context analysis”. Show a percentage only when real completed/total work supports it. Otherwise use the current stage and actual elapsed time.

Use M10–M12. The short moving track is the only repeated work indicator, and it settles to static text after its two cycles. Do not animate an invented profitable equity curve while computing.

If the backtest completes before context analysis, show the actual available result with **Analysis still running** and label incomplete sections. Do not postpone useful information just to wait for a cinematic reveal. The result reveal uses M13 once.

Provide **Continue elsewhere** if the job persists in the background and **Cancel run** if cancellation is supported. A cancel request reads “Cancelling…” until acknowledged; never claim the server stopped merely because the screen closed.

Failure copy names the stage and a usable next action: “Market history could not be loaded. Retry this step.” Keep the imported strategy and chosen assumptions. Resume completed work when supported.

## 11. Screen E — overview

Purpose: answer “How did my strategy perform, and what should I inspect next?”

Heading: the actual strategy name. Under it, one restrained metadata line: instrument, interval and tested dates. Top-level Explore is active; local Overview is active.

The original after-cost equity/return curve dominates the canvas. Directly label its endpoint with the actual net return. A second small line beneath the plot shows drawdown when it is needed to explain risk. Do not use three detached numerical cards.

Before a proposed filter has been independently evaluated, show only measured baseline results and descriptive findings. Never display the mockup's conditional verdict or an outperforming orange curve automatically. A provisional summary may say **A pattern worth testing** with “Historical finding” beside it.

At most two short findings may sit in free chart whitespace with thin connectors. Their anchor dates and sample sizes come from actual outputs. Selecting one opens B03. If a finding cannot be grounded, omit it.

After independent evaluation, an orange filtered curve and baseline comparison may appear with a clear label **Unseen history** and the exact period. Do not silently mix entire-history performance and unseen-test performance on the same scale.

Display an actual measured recommendation in plain language:

| Engine outcome | User-facing wording | Main next action |
|---|---|---|
| Keep | Keep as it is | Review paper test |
| Activate conditionally | Test with conditions | Review paper test |
| Reduce | Test a smaller allocation | Review paper test |
| Combine, if implemented | Test the combination | Compare strategies |
| Monitor | Keep watching | Inspect evidence |
| Kill/retire | Consider retiring this strategy | Review the evidence |
| Inconclusive | Not enough evidence | See what is missing |

Only show outcomes supported by the backend. Keep missing coverage, small samples or material uncertainty visible in one concise sentence near the conclusion. “Not enough evidence” is a normal completed result, not a broken screen.

Primary action before evaluation: **Explore conditions ↗**. Primary action after a suitable evaluation: **Review paper test ↗**. One primary action at a time.

Initial graph uses M13, hover M14–M16, pin M17 and findings M18. Returning from another tab restores the chart immediately; do not re-run the reveal.

## 12. Screen F — conditions

Purpose: show the relationship between historical performance and market conditions through coordinated graphics.

Heading: **Where does it work?** Local Conditions active. Small qualifier: **Historical patterns**.

Use three aligned tracks sharing one time axis and one movable date guide:

- Original strategy return: largest track, approximately 55% of graphic height.
- Trend: 20%, with defined units or a clearly labelled categorical state.
- Volatility: 25%, with its actual unit.

Do not put these in separate cards. Left labels are fixed in a common gutter. A cursor over any track updates the guide and readout across all three. The dates, observations and missing-data gaps remain aligned. State changes can be shown as understated ribbons beneath the relevant series, not glowing full-screen gradients.

Below the plot, use text choices for only the conditions the analysis actually supports. Examples: **Rising + calm**, **Sideways**, **Falling**. A condition choice highlights matching intervals; it does not delete other periods or quietly change the test population. B05/B03 states the selected sample and range.

A continuous numeric trend must not be depicted as a made-up smooth hill. A categorical regime is shown as a labelled strip. Use the correct visual form for the real measurement.

For sparse regimes, display **Too few trades** beside the selected state. A small distribution/interval mark can show uncertainty if the backend supplies it. Do not infer uncertainty bands from an arbitrary confidence percentage.

Selecting a condition opens B03 with the short finding, sample count and **Investigate pattern ↗**. The next view preserves the selected range. Keep a concise inline note: **A historical pattern is not yet a trading rule.**

Use M14 for the shared cursor, M20 for highlighting and M22 if the user selects a genuinely different dataset. Do not animate the three tracks independently out of sync.

## 13. Screen G — evidence and investigation

Purpose: explain a specific hypothesis and show what supports or challenges it.

Heading reflects the real question, for example **Why the losses?** Local Evidence active. The selected period from Conditions stays selected.

The main graphic aligns original strategy outcomes with the relevant explanatory variable. For a volatility hypothesis, use returns above volatility on the same axis. A thin vertical connector joins an observed loss event to its contemporaneously available context. Orange marks mean selected evidence, not proven causation.

A compact sentence below the graphic expresses the hypothesis, for example **Trade only when trend is rising and volatility is lower.** Label it **Proposed rule**. This copy must come from a structured, executable rule definition, not an unconstrained model sentence that cannot be simulated.

Selecting an event opens B03 with an actual date, short finding, sample count, qualifier and **Open evidence**. Opening evidence uses B10 and M25. Source details include title, publisher/tool, relevant timestamp and when the information was available. Keep external links available without forcing users into a permanent side panel.

News is optional evidence only when present. Missing news coverage receives a factual label. Never place fabricated headlines, implied causal stories or decorative news cards around the chart.

Show one concise counterpoint when available, such as **A simpler trend rule may explain the gain.** Rejected hypotheses are accessible through an inline **Other explanations** disclosure. No raw hidden reasoning transcript or stream of agent thoughts; show structured hypotheses, checks, outputs and limitations.

Primary action: **Test this rule ↗**. It records/freezes the candidate and starts the prescribed comparison. It does not modify the original strategy or immediately produce a favourable verdict.

Use M17 for the selected event, M18 for a finding, M25 for source details and M10–M12 for an actual evaluation job. A newly available insight only adds a small anchor via M32; it must not interrupt the user with a giant auto-opening bubble.

## 14. Screen H — comparison on unseen history

Purpose: let the user see whether the proposed filter adds value beyond the original and a simple alternative.

Heading: **Does the filter help?** Support line: **Same unseen period. Same costs.** Compare is active.

A thin chronology strip above the main plot labels **Learn · Choose · Unseen test**, with exact dates available on selection. It describes frozen chronological partitions. It is not a tuning slider that lets the user optimise against the held-out test.

Main plot: net returns for Original, Simple rule, Proposed filter and Cash, from a common starting value over the same test window. Direct line labels are preferred. A compact text legend with line swatches is permitted only when endpoint labels collide or series can be toggled.

Second plot: drawdown on the same time axis. Display actual maximum drawdown at the true low point, not automatically at the final point. The original and filtered identities remain consistent across both plots. Preserve enough vertical scale to show the worst loss honestly.

Under the plots, one short sentence summarises the actual comparison. Where available, expose uncertainty through **How certain is this?**, which expands a proper interval estimate or stability result with a plain-language explanation. Count trades and disclose unequal exposure or switching where relevant. Make deeper metrics available in an unboxed compact table on request.

An attractive hypothesis that fails receives the same polished treatment. Example: **The filter did not improve the unseen test.** Actions might be **Keep the original** or **Inspect the failures**, according to the actual policy engine. Never always highlight the candidate as a winner.

Changing costs or rules creates a new experiment version. Explain when a previously inspected test period is no longer untouched. Do not silently rerun model selection on the held-out results. Performance plots may be explored freely; descriptive zooming is not model retuning.

Primary action when allowed: **Review paper test ↗**. Use M22 on new result datasets and M23 for visibility toggles. No profit counters, upward-pointing decorative arrows or celebratory animation.

## 15. Screen I — review and freeze the paper experiment

Purpose: make the proposed action concrete before the user starts it.

Heading: **Review the paper test.** One-line explanation: **Run the original and filtered strategies side by side.**

Use a single readable vertical document, not a card grid. Show:

- Strategy name/version, presented in ordinary language with technical identifiers available in detail.
- Exact rule: conditions and allocation outcomes.
- Test duration: 14 days, start and expected review date.
- Starting simulated balance and explicit costs.
- Original benchmark and challenger.
- Risk/data-quality limits and what pauses the paper experiment.
- What the review will compare, and the possibility of insufficient evidence.

Example human-readable rule syntax: **If trend is rising and volatility is below the selected threshold, use the original allocation. Otherwise stay in cash.** Only show this when it matches the actual saved rule. Threshold values and definitions must be inspectable; do not substitute vague prose for the real configuration.

Editable items appear as underlined values. Altering a tested rule invalidates that comparison and requires the appropriate new evaluation. A simple date/start preference may be editable without pretending the policy itself changed.

One main action: **Freeze rules and start paper test ↗**. Nearby short statement: **Simulated trades only.** This is the human approval point. No auto-start when arriving at the screen and no redundant approval dialogue after the user has reviewed these details.

The button enters a pending state until the backend confirms a frozen experiment. Failure keeps all settings intact. Success uses M27 and enters Observe. The response includes a real policy/run identity; the interface does not invent one.

## 16. Screen J — observe the paper test

Purpose: compare actual accumulated simulated outcomes without implying early success.

Heading: **Day {n} of 14.** Under it: strategy name and **Paper test**. Observe active.

A slim sequence of 14 ticks indicates elapsed days. The current day is orange; future days are neutral and empty. Correctly handle day zero, timezones and completion. Do not show “Day 14” as proof of statistical validity.

One dominant plot compares original and filtered paper returns only through the latest actual observation. Add a drawdown track if relevant. Direct endpoints show latest measured values. No ghost forecast line continuing into future dates unless a separately labelled, explicitly requested forecast feature exists.

At the top right: **Rules frozen** and **View rules**. Beneath the plot: a short evidence-aware status such as **Too early to judge**, the actual completed-trade count and **View decisions ↗**.

New observations use M28. Updates follow the strategy cadence; an hourly strategy must not acquire a fabricated second-by-second heartbeat. Append new data without reanimating history. While the user is inspecting an earlier point, keep that selection stable; show a quiet **New observation available** action rather than yanking the cursor to the end.

Stale data uses M31 and an explicit **Last updated {time}**. Missing updates are gaps, not zero returns. The display distinguishes waiting for the next scheduled bar from a detected feed failure.

View decisions expands an unboxed table with decision time, condition, target allocation and a factual explanation/source link. No claim that the LLM directly placed an order.

At completion, heading becomes **14-day review**. Show the measured conclusion, including **Still inconclusive** when appropriate. An extension requires an explicit action and preserves the original period. Retuning creates a new challenger, not a silent modification of the frozen run.

## 17. Chart interaction contract

Apply this contract to every chart unless a screen explicitly specifies a categorical strip or step plot.

1. Every plot has a clear quantity, unit, date range and data basis: historical, unseen historical or prospective paper.
2. Put axis labels in the shared margin. Use sparse ticks: typically 4–5 x-ticks and 3–5 y-ticks on desktop; 3 x-ticks on mobile. Do not remove units to look cleaner.
3. Use direct series labels where possible. Resolve collisions with a minimum 18px vertical separation and a short leader line. Never overlap values or clip the final label offscreen.
4. Keep the same series identity across pages: original light neutral, simple rule dashed neutral, proposed filter orange, cash dotted neutral.
5. Hover/focus/tap selects an actual observation or interval, not an invented intermediate financial value. The guide snaps to the selected timestamp and all readouts use that same time. Explain interval aggregation when applicable.
6. Keyboard users can focus the chart's labelled interaction control and step observations with Left/Right; Home/End jump to boundaries; Enter pins; Escape clears. Provide a nearby **View data** alternative with a semantic table. Do not create thousands of tab stops.
7. On touch, tap pins a reading. Dragging a visible date scrubber moves the selection. Ordinary page scrolling remains available; do not capture all one-finger gestures on the chart.
8. A range brush is available through a labelled **Select period** control; it does not happen accidentally during scrolling. Clear selection restores the whole period without rerunning the experiment.
9. Use faithful raw/step/linear plotting for observations. For dense visualisation, reduce points with an extrema-preserving approach and retain full data for calculations/readouts. No decorative spline may create a new peak, erase a trough or imply a continuous position when it is discrete.
10. Missing data creates a gap with an inspectable coverage note. Do not bridge a long outage or future-fill a feature.
11. Comparisons use aligned timestamps and the same value basis and axis scale. Visibility toggles do not opportunistically rescale an apparently worse series into looking better.
12. Axis-range changes are explicit and atomically applied. Unrelated datasets crossfade rather than morphing through fictitious shapes.
13. No randomly animated fake points, “live” badges on static history or invented uncertainty bands.
14. Make plotted data available through **Download data** where implemented. Download events describe the actual included series, dates and units.

## 18. Loading, empty, error and negative states

Minimal design must be fully designed when things go wrong.

| Situation | Visible response | Action |
|---|---|---|
| No strategy yet | Add your strategy | Choose file / Try an example |
| Unreadable file | We could not read this file | Choose another file; details available |
| Missing column | Choose the column containing target positions | Open column editor |
| Ambiguous time unit/timezone | Confirm how these times should be read | Show real timestamp examples |
| Insufficient position history | This file supports diagnosis, but not this backtest | Explain required input or offer valid diagnosis path |
| No market-history coverage | No supported data for this period | Change period/source |
| No trades | The strategy did not trade in this period | Inspect positions or change test period |
| Too little condition data | Too few trades to judge this condition | Inspect another condition / see counts |
| No useful hypothesis | No supported filter found | Keep baseline visible; inspect evidence |
| Candidate fails | The filter did not improve this test | Inspect failures / retain original according to measured outcome |
| Uncertain result | Not enough evidence | Explain missing evidence; do not fabricate a verdict |
| Run failure | {Stage} could not finish | Retry valid step; keep inputs |
| Offline while viewing history | Offline — showing saved results | Retry connection; visible saved time |
| Paper feed stale | Waiting for data since {time} | Inspect feed; apply configured safeguards |
| Submission uncertain | Checking whether the run started | Resolve existing request before allowing duplicate creation |

Reserve chart dimensions while loading. Use a static thin axis outline or plain “Preparing results” text; no shimmer-card grid. For operations shorter than 150ms, avoid flashing a loading surface. Persistent errors remain visible until resolved or dismissed appropriately.

## 19. Responsive composition

Desktop ≥1200px: open full-width canvas; top wordmark left, four navigation labels right; title and short status can share a row; charts occupy approximately 65–75% of first-view content area on result screens.

Tablet 768–1199px: reduce margins and heading size modestly; place long status text below the heading; maintain the shared-axis plot composition; direct labels may move beneath endpoints with leaders.

Mobile 320–767px: keep the wordmark and a small labelled **Navigate** control in the header. A temporary menu lists the four destinations vertically. Do not reintroduce a permanent bottom tab bar or left drawer. Use a 34px heading and 14–16px controls. Chart height is normally 260–320px. Related tracks stack while retaining a shared time axis. The next action follows the chart in normal flow; never cover data with a fixed CTA.

At narrow widths, B03/B06 may become an opaque bottom-aligned modal sheet with appropriate focus trapping, labelled close button and safe-area padding. It opens only through explicit selection. Do not place critical text offscreen or require horizontal page scrolling.

Prefer shortening labels, reducing optional annotations or stacking content to shrinking text. Keep touch targets at least 44×44px through invisible hit padding. Verify at 320px, 390px, 768px, 1024px, 1440px and 1920px, including 200% text zoom.

## 20. Accessibility and user control

- Respect `prefers-reduced-motion`; offer a quiet **Motion: System / Reduced / Full** setting in a temporary Display menu. System is default, and a user's explicit choice persists.
- Reduced removes movement, scale, drawing, loops and auto-morphs. Use immediate state changes or brief opacity transitions. Direct manipulation still follows the user's input.
- No autoplay sound, flashes or motion that continues merely to make the interface look alive.
- Hover/focus explanations are dismissible, hoverable and persistent while in use. Essential information and actions remain available without hover.
- Use visible keyboard focus, semantic controls, correctly labelled popovers and proper modal focus management. Return focus to the triggering control when closing.
- Nonmodal chart exploration does not trap focus. Mobile modal editors do trap it while open.
- Announce important stage changes and completion through a polite live region. Do not announce every pointer move or animated frame.
- Associate errors with their fields and move focus to a useful error summary only when an attempted submission fails. Do not steal focus for a background event.
- Validate ordinary text contrast at least 4.5:1 and large text at least 3:1; ensure essential graph/control marks are distinguishable. Decorative hairlines are not the only affordance for an input.
- Pair series colours with line styles and labels. Do not force users to distinguish orange from grey alone.

## 21. Technical behaviour that supports the design

Keep this implementation detail out of the user-facing interface.

- Use one central token set for colour, spacing, typography and motion; every screen consumes it.
- The existing Next.js/Tailwind chart stack is acceptable. Select one motion system and prevent its defaults from adding arbitrary bounce or layout shifts. Prefer CSS transforms/opacity for controls.
- Render data as actual chart primitives, never a generated screenshot used as a functional graph.
- Use responsive SVG for moderate series and an appropriate canvas path for high density; measure the real container. Avoid resizing a fixed-size desktop screenshot into mobile.
- Process expensive joins/downsampling off the main interaction path. Pointer readout work should be small and bounded.
- Cancel obsolete requests or discard stale responses by experiment/selection identity. A slow earlier request must not overwrite a later choice.
- Use explicit backend states for file validation, queued/running/completed/failed/cancelled jobs and paper experiment states. Animate these states; never use animation timers as business logic.
- Use idempotent run creation. Disabled buttons alone are not duplicate-submission protection.
- Pause nonessential animation in hidden tabs. Disconnect observers and remove listeners on unmount. Do not leave endless requestAnimationFrame loops when the interface is static.
- Target smooth interaction within a 16.7ms frame budget on an ordinary laptop; verify rather than claim this by default. Cached navigation should visibly respond within roughly 100ms; long computations remain honest asynchronous jobs.
- Self-host/pin dependencies according to the project environment and verify relevant APIs during implementation. Do not assume a library version solely from this brief.
- All example fixtures are labelled. Production output uses measured values and real uncertainty from the backend. The UI is not allowed to manufacture research outputs to match the visual concept.

## 22. Interaction walkthrough to implement and inspect

Use this as a connected product rehearsal, with timings driven by actual event completion rather than an artificial demo timeline.

1. Entry settles via M01. User chooses a supported signal file.
2. Filename appears via M06. Actual data checks update via M07. Mapping errors remain fixable inline.
3. User opens Period through B06, changes dates, saves via M09 and reviews visible costs.
4. User starts the backtest. The action acknowledges immediately; backend progress follows M10–M12.
5. Actual results become available. The graph reveals once via M13; endpoint values are already readable.
6. User selects a point. All coordinated values update at one timestamp; B01 appears, and a pin uses M17.
7. User chooses Conditions. The selected time persists; linked tracks appear without a new fictitious result.
8. User selects Rising + calm. Real intervals highlight via M20. B03 shows its sample and uncertainty.
9. User opens Evidence. A selected event remains aligned to its context; an evidence detail expands via M25.
10. User tests the actual proposed rule. Backend evaluation runs; Compare receives the frozen unseen-period results.
11. User toggles a series and inspects uncertainty. Any negative result remains equally visible.
12. User enters Review. The frozen rule, period, costs and risks are readable before approval.
13. User starts the paper experiment. Confirmation comes from the backend via M27.
14. Observe appends only real new observations via M28. A feed outage freezes the plot and displays the actual last-update time.

Repeat this rehearsal with Reduced motion, keyboard only, touch input, an invalid file, a no-trade strategy, a failed filter, an inconclusive result and a stale feed.

## 23. Acceptance criteria

The implementation is not complete merely because the first screenshot looks attractive.

### Visual

- Every page shares one open black canvas, the same orange and the same type hierarchy.
- No sidebar, card grid, boxed chart area or generic assistant widget has slipped back in.
- Major result graphics occupy the intended visual focus; text explains decisions rather than filling space.
- Source details, long rule definitions and advanced assumptions remain available without taking over the first view.
- All labels, endpoints, axes and temporary bubbles remain readable and unclipped at the tested widths.

### Product

- The entry screen says Add/Test your strategy and explains supported input; it does not ask for a completed backtest.
- All navigation and primary actions lead somewhere useful and preserve the correct experiment context.
- The platform performs the stated calculations; progress is event-driven and numbers are measured or visibly labelled fixtures.
- Historical diagnosis, unseen evaluation and paper results cannot be mistaken for each other.
- The original strategy stays unchanged; an actual frozen paper policy requires explicit user action.
- Missing information, negative results and uncertainty are represented honestly.

### Motion and bubbles

- Every animation corresponds to M01–M36 and every bubble to B01–B10, or an explicitly documented justified extension.
- At rest, the interface is still. Hover feedback is quiet, and the user controls exploration.
- Bubbles open near their evidence, avoid covering the selected mark and remain usable with keyboard and touch.
- Rapid repeated input does not queue transitions, generate duplicate jobs or display stale results.
- Reduced motion removes nonessential movement throughout the application.

### Delivery

Implement all core views and all meaningful loading, error, negative and empty states. Check the connected flow, not only individual components. Supply the coherent result and a concise statement of what is real, what uses fixtures and what backend capability remains unimplemented. Do not silently label a visual-only prototype as a working research system.

The final effect should be calm when idle, precise when used, and memorable because the data is beautifully presented. Minimalism is the discipline of choosing the next useful thing to show.

---

## Reference notes outside the implementation prompt

This brief adapts the supplied Keep or Kill project specification and the user's corrected flow: the platform performs backtesting and analysis from a supported strategy input. It replaces the rejected sidebar/card direction and the incorrect “Drop a backtest” copy. The numerical mockups are style references, not datasets.

The exact layouts, palette, timings and interaction choices above are proposed creative decisions. The following primary references support the font choices and accessibility behaviour; they do not prescribe this visual design:

- [Instrument Serif project](https://github.com/Instrument/instrument-serif)
- [Geist fonts](https://vercel.com/font)
- [W3C Animation from Interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions) — support disabling nonessential motion.
- [W3C Content on Hover or Focus](https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html) — contextual content should be dismissible, hoverable and persistent while used.
- [W3C Contrast Minimum](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum) — text contrast.
- [W3C Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast) — essential control and graphic contrast.
