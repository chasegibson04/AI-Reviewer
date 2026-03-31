# Reverification of Previous Pass

## Summary
The previous improvement pass made several claims about the repository's state. A thorough code and behavior audit was conducted to independently verify these claims.

## Findings Matrix

### Confirmed True
- **DOCX-native handling improved:** The pipeline successfully handles pre-annotated DOCX files, preserving text and cleanly stripping prior AI comments.
- **Medium-tier model leaving `evidence_source` null:** The models often defaulted to omitting the source when it wasn't explicitly clear.
- **Project 1 and 2 comment quality:** Comments remained generic, missing specific physical constraints and specific critiques of "fully automated" claims.
- **Citation fetcher aggressive downloading:** The fetcher did indeed retrieve PDFs.
- **Insecure retrieval behavior:** The fetcher actively bypassed TLS verification on retries (`verify=not is_retry`) and used spoofed Chrome/Windows User-Agents.

### Partially True
- **Assertion verification using support-paper chunks:** The code to chunk and verify was present, but semantic ingestion was bottlenecked. A flawed relevance algorithm (Jaccard index of 20,000 chars) effectively blocked most retrieved papers because large documents mechanically deflate the Jaccard intersection ratio.

### False / Overstated
- **ReviewSchema forcing `evidence_source`:** The schema (`ReviewSchema` and `GroundedComment`) explicitly allowed `None`, and the repair layer would quietly default to `None` if the model omitted it.
- **Retrieved PDFs semantically ingested:** Beyond the algorithm bottleneck, an arbitrary hard cap of 20 `support_materials` truncated retrieved citations if the project had existing materials.

## Corrective Action Taken
We resolved these discrepancies by fixing the relevance calculation, adjusting the materials cap, explicitly patching the repair layer to use meaningful non-null fallback states (`manuscript_internal`), and scrubbing the insecure TLS/User-Agent behaviors.