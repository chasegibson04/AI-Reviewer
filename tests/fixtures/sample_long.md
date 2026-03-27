# Sample Long Paper

## Abstract
This is a longer fixture document used to stress test context chunking and structured review generation. The text intentionally contains multiple sections and repeated claims so benchmarking and smoke tests can exercise retrieval and parse-repair pipelines.

## Introduction
Peer review quality is highly sensitive to prompt framing, model reliability, and schema constraints. In local-first workflows, this sensitivity is amplified because available model sizes and decoding behaviors vary significantly.

## Related Work
Prior systems often assume cloud APIs and weakly enforce structure. This fixture pushes local tools toward deterministic reporting by requiring strict schemas, traceable artifacts, and explicit warning channels.

## Methods
We split documents into chunks and optionally compute embeddings for retrieval. During generation, a primary model produces review JSON. If the output is invalid, a repair path attempts local fixes and optionally invokes a dedicated repair model.

## Experiments
We evaluate format compliance, latency, and fallback frequency. We also verify that parser warnings are surfaced for low-quality extracts and that outputs include machine-readable metadata.

## Discussion
Results suggest that robust formatting requires layered safeguards rather than a single prompt instruction. Models may still drift from schema under long contexts or ambiguous inputs.

## Conclusion
A local-first review system can be practical if it ships with diagnostics, strict defaults, and explicit failure handling.
