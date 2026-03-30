# AI-Reviewer Architecture

`ai_reviewer` is organized around local-first editorial review with auditable run artifacts.

## Core Modules

- `config.py`: layered YAML configuration plus env overrides
- `models/ollama_provider.py`: local Ollama chat/embed provider with strict-offline URL checks
- `models/selector.py`: model typing, deep-run routing modes, embed/chat safety
- `ingest/loaders.py`: PDF/TXT/MD/DOCX/TEX parsing
- `ingest/chunking.py`: chunking for review and retrieval
- `ingest/retrieval.py`: local embedding retrieval
- `review/engine.py`: standard review orchestration, support filtering, artifact writing
- `review/deep_run.py`: staged deep-run orchestration, context-pack compliance, final synthesis
- `review/manuscript_annotation.py`: comment anchoring, rewrite generation, abstention, manifests
- `review/citation_fetcher.py`: pre-run citation fetch with verification labels and query policy
- `tools/docx_tools.py`: DOCX annotation-state inspection, comment/suggestion writing, validation
- `review/render.py`: markdown/text/docx report rendering
- `output_verifier.py`: post-run artifact verification
- `cli.py`: Typer/Rich CLI and guided launcher routing

## Safety Defaults

- strict offline enabled by default in repo defaults
- Ollama must be localhost/127.0.0.1 in strict offline mode
- embedding models are not allowed in chat stages
- multimodal models are not routed into text-only deep-run stages
- output verification runs after major workflows

## Project Model

Project-scoped runs live under:

```text
projects/<project_id>/
  materials/
  runs/
  evaluations/
  audits/
  cache/
```

The architecture is manuscript-first:
- `materials/manuscript` is the primary source lane
- `materials/other` is supporting-context only
- support materials are filtered before grounding

## Deep-Run Architecture Notes

Deep-run now has explicit routing modes:
- `default`
- `max_quality`

The selector owns stage-model routing; `deep_run.py` consumes the resolved stage stack and writes:
- `deep_run_plan.json`
- `stage_model_stack.json`

A bounded `final_arbitration` pass exists after reconciliation, but current benchmark evidence shows this stage is still limited more by schema quality than by raw model strength.

## DOCX Architecture Notes

Native DOCX handling now records annotation state and distinguishes:
- clean native DOCX
- DOCX with existing comments
- prior AI-Reviewer annotated DOCX

Validation artifacts explicitly track:
- `new_ai_reviewer_comments_added_count`
- `new_suggested_change_blocks_added`
- `meaningful_new_review_state`
- `silent_noop_suspected`

## Known Limitations

- final synthesis still falls back too often in deep-run
- figure review is still text-only on validated paths
- suggested revisions are visible suggestion blocks, not Word track changes
