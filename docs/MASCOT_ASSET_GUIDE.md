# Keep / Kill mascot asset guide

This pack contains 24 static poses in four transparent PNG atlases and a separate homepage duo, generated with the built-in image-generation tool from the user's supplied references on 8 November 2026. The cream/plum product now uses all 24 poses through contextual states and the separate duo on the homepage. `src/components/redesign/mascot.tsx` reads the manifest for every crop. Open `/mascots/v1/index.html` for the visual asset gallery; `manifest.json` supplies exact cell coordinates, and `prompts.json` records the generation prompts.

## Art direction

Use the supplied reference boards as the source of truth:

- **Bull:** tall, angular orange silhouette; large curved horns; cream oval muzzle; small orange nostrils; dark plum dash eyes and expressive brows; sparse dark plum contour marks.
- **Bear:** rounded, stocky lavender/periwinkle silhouette; cream muzzle; dark plum nose; low-lidded skeptical brows; a few dark contour marks for paws and fur.
- **Shared treatment:** warm editorial flat illustration, hand-drawn contour lines, a tiny amount of paper grain, strong negative space, no gradients, no 3D rendering, no glossy shading, no text inside the art, no charts or numbers baked into the image.
- **Palette direction:** tangerine `#ff681b`, lavender `#9389df`, cream `#fffaf1`, deep plum `#241626`. The generated art has subtle color variation inside the silhouettes and transparent space outside them; no ground shadows are baked in.

## Delivered files

Each sheet is a 1536 × 1024 RGBA PNG with six 512 × 512 cells in a 3-column by 2-row layout. Keep the cell order and names stable so the eventual sprite component can address a pose by index. These are distinct static poses, not frame-by-frame animation sequences. Upper-body and full-body compositions have different visible heights; choose the appropriate pose for the available space.

| File | Cells, left to right then top to bottom | Intended role |
| --- | --- | --- |
| `apps/web/public/mascots/v1/bull-explain.png` | `point-left`, `point-right`, `present-up`, `welcome`, `compare`, `neutral` | Short findings and chart annotations |
| `apps/web/public/mascots/v1/bull-research.png` | `magnifier`, `read-sheet`, `take-note`, `frame-region`, `thoughtful`, `acknowledge` | Evidence, conditions and setup guidance |
| `apps/web/public/mascots/v1/bear-explain.png` | `point-left`, `point-right`, `present-up`, `question`, `compare`, `neutral` | Weak, mixed or uncertain findings |
| `apps/web/public/mascots/v1/bear-research.png` | `magnifier`, `read-sheet`, `chin-rest`, `folded-arms`, `pause`, `waiting` | Holdout, limits and paper-plan guidance |
| `apps/web/public/mascots/v1/hero-duo.png` | Bull standing beside a reclining bear, transparent background | Homepage hero / story end frame |

The standalone duo can be wider than a sheet cell. Keep both characters fully visible, with the bull higher and active on the left and the bear lower and cautious on the right, matching the supplied homepage reference.

## Product mapping

Use one mascot at a time beside the supplied evidence. The character is an annotation layer, never a decision-maker or a buy/sell signal.

| Surface | Default pose | Example accessible callout |
| --- | --- | --- |
| Strategy / import | No mascot by default; optional `welcome` after a valid preview | “Your file is ready to check.” |
| Overview | `bull-explain` `point-left` or `point-right` when a recorded stretch is selected | “This stretch contributed most of the recorded result.” |
| Conditions | Bull `present-up` for a supported cluster; bear `present-up` for a weak or mixed cluster | “The supplied evidence is strongest in this condition.” / “The supplied evidence is mixed here.” |
| Evidence | Bull `acknowledge` for supported findings; bear `pause` for rejected or uncertain findings | “Supported by the recorded evidence.” / “Keep this explanation provisional.” |
| Compare | Bull `compare` for the proposed rule; bear `point-right` toward unseen or held-out dates | “Compare the two supplied series.” / “Check the unseen window before drawing a conclusion.” |
| Paper plans | Bear `waiting` or `folded-arms` beside planned-only status | “This plan is saved, not running.” |

Copy must remain in normal HTML so it can be read by assistive technology and translated. Do not place claims, metric values, dates, or labels inside the PNG.

## Motion and accessibility

- Latest direction: mascots are primary editorial scenes, never tiny icons or enclosed cards. On desktop the main character box is usually 280–380px, with an outlined cream/plum speech bubble and one short accessible explanation. On phones the box is usually 210–280px; the character peeks inward from the right edge while keeping the face and upper body visible. The text remains in normal HTML and never covers controls.
- `MascotCallout` observes its own visibility once per pose. It disconnects after entry and on unmount; reduced motion renders the settled pose immediately. Poses are distinct static editorial states, not a frame-by-frame animation sequence.

- Use a 480–560ms opacity/translate/rotate entrance for the character, then a 120–180ms speech-bubble pop. A restrained 4–6px idle drift may run only while the scene is visible; pause it offscreen or when the document is hidden.
- A selected chart point may add a 1–2px positional nudge once. No blink frames are supplied in this pack. Do not loop a large reaction continuously or compete with chart movement.
- Use a hand-drawn-looking speech bubble or annotation sibling in HTML. A guided explanation may dim the page, spotlight one real target, and draw a round-cap SVG arrow from a large bottom-right mascot to that target. Its dismissal returns focus to the chart control, finding, or action that opened it.
- Set meaningful `alt` text only when the pose conveys information. For decorative use, set `alt=""` and repeat the meaning in nearby text.
- Start with a 280–380px scene box on desktop and 210–280px on mobile. Atlas cells include transparent breathing room, so the box must be larger than the visible foreground. Never let the mascot cover the selected date, legend, primary action, or the target in a guided explanation.
- With reduced motion, show the final pose immediately and remove the nudge, blink and stagger.

## Asset QA checklist

Before wiring a file into the app, confirm:

1. PNG has a real transparent background and no white rectangle.
2. All six cells share the same dimensions and no figure crosses a cell boundary.
3. Bull and bear remain recognisable at the actual chosen display size.
4. Plum contour lines are crisp at 1x and 2x display density.
5. No text, fake data, trading instruction, logo variation or watermark is embedded.
6. The character’s meaning is still clear when the adjacent callout is hidden.
7. The asset is not used to imply a measured result, live trade or paper observation that the API did not provide.
