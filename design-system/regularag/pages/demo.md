# Demo workspace override

Based on the verified UI/UX Pro Max search `education knowledge search calm`:
Knowledge Base/Documentation, FAQ/Documentation pattern, Minimalism & Swiss Style.
Stack search: HTML/Tailwind grid gaps/semantic tokens; equivalent native CSS used.
UX search: long-request feedback, stable busy state/focus and readable long content.

- Single-origin FastAPI + native HTML/CSS/ES modules; no build step/CDN/runtime UI dependencies.
- Keep MASTER slate/blue/light palette, high-contrast white cards, 4/8px rhythm.
- Atkinson Hyperlegible if available locally, then Segoe UI/system sans for Vietnamese;
  no external font request. Sans-serif display title and restrained geometric decoration.
- Desktop rail + question workspace + evidence column; at <=1100px rail becomes topbar,
  at <=760px stack question/result/source sections. No fixed overlays obscuring content.
- Stable color/border hover and visible focus; no translating cards/buttons on hover.
- Icon family: inline Lucide-style stroke SVG, decorative icons aria-hidden.
- No confidence meters, invented stage percentages or fake token streaming. Pending
  request shows elapsed time, aria-busy, honest CPU loading note and client stop-waiting.
- Answer is backend text. Citation buttons resolve only source IDs actually returned;
  source URLs allow HTTP/HTTPS; all source/user/model strings render through text nodes.
- Clarification retains original question and lets the user fill explicit scope fields.
- Feedback is session-local; JSON export contains the real request/response for manual review.
- Presets use already-exercised development questions; held-out dataset is not exposed by UI.
