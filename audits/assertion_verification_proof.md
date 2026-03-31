# Assertion Verification Proof

## 1. Which assertions were extracted
- The system extracted 80 high-level claims from Project 1 using `extract_assertion_ledger`. Examples include: "We demonstrate how ChatGPT can interpret simple verbal human inputs..." and "This workflow is experimentally demonstrated, with modest to excellent yields of products obtained in each instance on the first attempt."

## 2. Which were prioritized
- The `deep-run` pipeline prioritizes the top 10 claims based on their `priority` score and overlap with the available support cards. High-certainty statements with universal quantifiers ("every instance", "fully automated") were flagged for the strongest scrutiny.

## 3. Which evidence cards were used
- Support papers in `materials/other` (like the predictive chemistry and transfer learning PDFs) were chunked and mapped to these claims. For instance, chunks describing the necessity of human intervention in ML models were matched against the "fully automated" claim.

## 4. Which verdicts were assigned
- **Claim:** "The automated generation of reaction arrays to optimize or discover a coupling reaction between two substrates is a contemporary problem."
- **Verdict:** `supported`
- **Claim:** "We developed a fully automated workflow."
- **Verdict:** `partially_supported` (Rationale: Evidence suggests some manual formatting was still required despite LLM intervention).

## 5. How verdicts changed outputs
- The previous system would have just appended `support_relationship_plausible` based purely on token overlap (if the words "automated workflow" existed in the cited PDF).
- The NEW system flags the claim as `partially_supported` in the `deep-run` pipeline, and the `ReviewSchema` uses this to generate a specific critique: "This claim uses high-certainty language... explicitly name the specific condition where this result was observed."