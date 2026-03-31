# Support-Paper Usage Proof

## 1. Project 1: `20260325163524_test-existingphactorpaper`
- **Support file available:** `materials/other` contains several PDFs, including `Accelerating_Reaction_Optimization_with_a_Machine_Learning_Framework_Base.pdf` and `Predicting_reaction_conditions_from_limited_data_through_active_transfer_learnin.pdf`.
- **Support file parsed:** The `support_ingest_report.json` and `support_material_filtering.json` show these PDFs were successfully parsed into text and chunked.
- **Support file selected:** The system filtered out low-overlap files (like standard journal instructions if irrelevant) but kept the ML optimization papers based on a >0.04 overlap score.
- **Support file cited in verdict:** The `deep-run` Stage 5b (`_verify_claims_semantically`) explicitly used these chunks as "evidence cards." For example, when verifying the claim that the model could predict reaction conditions, the semantic verifier checked it against chunks from `Predicting_reaction_conditions_from_limited_data_through_active_transfer_learnin.pdf`.
- **Support file ignored:** Any files with <0.04 overlap or matching the manuscript exactly (>0.95 overlap) were marked `skipped` and dropped from context.

## 2. Project 2: `20260327051312_miniaturization_d2b`
- **Support file available:** `materials/other` contains documents related to high-throughput experimentation.
- **Support file parsed:** Parsed successfully.
- **Support file selected:** The context pack and other relevant PDFs were injected into the `engine.py` context prompt.
- **Support file cited in verdict:** The resulting `ReviewSchema` output for this run successfully utilized the `evidence_source` field, explicitly citing the missing `limitations_statement` from the context constraints and pointing to the general procedure section when critiquing missing controls.
