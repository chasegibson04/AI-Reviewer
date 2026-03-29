# Current State Note (Quality + Pre-Run Paper Download)

Date: 2026-03-28

Approved projects inspected:
- 20260325163524_test-existingphactorpaper
- 20260327051312_miniaturization_d2b

Observed failure modes before this pass:
- Comments could still include low-sanity suggestions in edge cases.
- Sentence-level issues were often anchored to entire paragraph ranges.
- Suggested-changes DOCX used silent paragraph replacement (original text not visibly preserved).
- Citation fetch existed but was monolithic and not easy to extend with new retrieval methods.
- Citation downloads happened pre-run, but support-material parsing for the same run was based on pre-download inventory.

Changes targeted in this pass:
- Added deterministic absurd-comment filtering.
- Added sentence anchor propagation (`anchor_text`) for tighter comment range targeting.
- Changed suggested-changes DOCX output to visible in-text proposals (`original + [Suggested change] revised`).
- Replaced citation fetch monolith with method registry + configurable method order.
- Added pre-run citation stage logs and per-run method attempt reporting.
- Refreshed project support-material parsing after citation download so same run sees newly downloaded papers.
