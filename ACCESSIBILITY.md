# Accessibility

datavisual.studio aims to meet **WCAG 2.2 Level AA**. Accessibility is treated as a property of the
components, not a pass bolted on at the end — so it holds as the product changes.

## What's verified

- **Automated:** [`@axe-core/playwright`](frontend/e2e/axe.spec.js) runs on `/`, `/about`, `/demo`,
  `/studio` and a built dashboard on every push in CI, and must report **zero critical or serious
  violations**. The scan emulates reduced motion and waits for entrance animations to settle so it
  measures the state a user actually sees.
- **Colour contrast:** the neutral text ramp meets AA on the dark surface (secondary text ≈ 7:1,
  tertiary ≈ 5.9:1); status colours and the focus ring were chosen against their backgrounds.
- **Charts are readable to screen readers** — a data-viz product's core gap. Every chart is
  `role="img"` with a label generated **from the plotted numbers** (not the LLM), plus a **"View as
  table"** toggle. Confirmed on the public `/demo` and `/share` surfaces, not just the editor.
- **The assistant is a live region** (`aria-live`) so asynchronous answers are announced.
- **Focus management** — the thing axe can't test. Every modal, drawer and overlay traps focus while
  open, closes on Escape, and returns focus to the trigger; the mobile navigation and assistant
  drawers are `inert` when closed. Exercised by a keyboard-only end-to-end test.
- **Motion:** every animation honours `prefers-reduced-motion` (a global backstop plus per-animation
  settling); reveals degrade to visible so no content is gated behind a transition.
- **Structure:** a skip-to-content link, landmark regions, and keyboard-operable controls sized to
  the WCAG 2.2 24×24 px target minimum.

## Known gaps (stated, not hidden)

- A full manual screen-reader pass (VoiceOver / NVX) across every screen is ongoing; automated axe +
  the keyboard e2e cover the common cases but not everything a human tester would catch.
- A couple of secondary screens (`/admin`, error pages) haven't had a dedicated landmark/heading
  audit yet.
- Some chart types produce a terse aria-label (range + type) rather than a rich description.

## Reporting

Found a barrier? Please open an issue at
<https://github.com/4mohdisa/datavisual.studio/issues> or email **mohdisa233@gmail.com**. Accessibility
reports are prioritised.
