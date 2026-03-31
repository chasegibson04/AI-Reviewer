# Citation Checking Proof

## 1. What references were extracted
- `citation_fetcher.py` extracted 24 formatted references from Project 1's bibliography.

## 2. What metadata was checked
- DOIs were extracted via regex (e.g., `10.1038/s41586-018-0084-2`).
- The system queried OpenAlex, Unpaywall, and (now) Semantic Scholar and Europe PMC to resolve the metadata.

## 3. What citation-to-claim links were attempted
- `build_claim_to_citation_map` mapped in-text citation markers (e.g., `[6]`) to the bibliography list.

## 4. What the system really knows versus does not know
- **KNOWS:** The system knows if a DOI exists, if the title in the bibliography matches the DOI record (`metadata_match_likely`), and if a local PDF exists in `materials/other`.
- **DOES NOT KNOW:** The general pipeline does *not* know if the remote paper actually supports the claim (unless it is downloaded and run through the `_verify_claims_semantically` stage).

## 5. Where final outputs mention mismatch/weak support
- The resulting JSON explicitly applies the label `support_relationship_not_verified` to every external citation unless it was parsed locally. 
- The `format_compliance_report` now flags large numerical gaps (e.g., jumping from `[2]` to `[20]`), which was incorporated into the main `review_report.md` as a citation formatting warning.