# Validation Matrix Run

| Project | Run ID | Input Type | Profile/Mode | Models Used | Support-Material State | Verification State | Outputs Produced | Qualitative Judgment |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `20260325163524_test-existingphactorpaper` | `20260330_165001_review` | DOCX | Deep | `gemma3:27b`, `mistral-small3.1:24b` | Active (parsed 12 docs) | Semantic claims checked; DOIs resolved; formats checked | JSON manifests, `.md` reports, annotated DOCX | **Pass**. The system caught long formatting in sections and flagged methods concerns. Revisions are no longer just mechanical word-chopping. Semantic verification produced 'partially_supported' on claims about fully automated workflows. |
| `20260327051312_miniaturization_d2b` | `20260330_172354_review` | PDF | Deep | `gemma3:27b`, `mistral-small3.1:24b` | Active (parsed 14 docs) | Semantic claims checked; DOIs resolved; formats checked | JSON manifests, `.md` reports, annotated DOCX | **Pass**. The system accurately identified missing experimental controls. The new `evidence_source` constraints forced the LLM to cite specific page sections rather than generic "clarify this" comments. |
