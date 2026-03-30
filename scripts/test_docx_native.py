import os
import json
from pathlib import Path
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.review.manuscript_annotation import build_annotated_manuscript_output
from ai_reviewer.models.ollama_provider import OllamaProvider
from ai_reviewer.config import load_config
from ai_reviewer.review.schema import ReviewSchema

def test_synthetic_docs():
    cfg = load_config()
    provider = OllamaProvider(cfg.defaults.ollama_base_url)
    out_dir = Path("audits/docx_native_fixtures")
    
    from ai_reviewer.review.schema import ReviewSchema, Recommendation
    
    # Mock review
    review = ReviewSchema(
        summary="Test summary",
        recommendation=Recommendation(decision="revise", rationale="Test"),
        confidence=0.8,
        detailed_reviewer_comments=["This is a test comment from the LLM."],
        section_specific_comments=[
            {"section": "Introduction", "comment": "Test intro comment.", "severity": "medium", "evidence_source": "none", "manuscript_quote": "This is an introduction paragraph."}
        ],
        extracted_action_items=[
            {"action": "Fix intro.", "priority": "high", "owner": "author", "evidence_source": "none"}
        ],
        model_debug_metadata={"provider": "test", "model": "test", "temperature": 0}
    )
    
    for filename in ["clean_native.docx", "human_commented.docx", "ai_commented.docx"]:
        source = out_dir / filename
        if not source.exists():
            continue
            
        doc = parse_file(source)
        run_out = out_dir / f"output_{filename.replace('.docx', '')}"
        run_out.mkdir(exist_ok=True)
        
        print(f"Processing {filename}...")
        result = build_annotated_manuscript_output(
            source_path=source,
            doc=doc,
            review=review,
            output_dir=run_out,
            provider=provider,
            model="phi4-reasoning:latest",
            rewrite_model="mistral-small3.1:24b"
        )
        
        print(f"  Annotation state: {result['source_mode']['annotation_state']}")
        print(f"  Comments added: {result['comments_added']}")
        print(f"  Pre-annotated policy: {result.get('preannotated_docx_policy')}")
        print("  ---")

if __name__ == "__main__":
    test_synthetic_docs()
