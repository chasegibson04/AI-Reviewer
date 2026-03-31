import json
import logging
import sys
from pathlib import Path
from ai_reviewer.config import load_config
from ai_reviewer.models.ollama_provider import OllamaProvider
from ai_reviewer.review.manuscript_annotation import _reflection_pass, _adjudication_pass
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.models.base import ChatRequest

# Ensure stdout handles unicode
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

logging.basicConfig(level=logging.INFO)

def _chat_json(provider, model, system_prompt, user_prompt, timeout_seconds):
    try:
        resp = provider.chat(
            ChatRequest(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=3000,
                timeout_seconds=timeout_seconds,
                metadata={"json_mode": True}
            )
        )
        from ai_reviewer.review.repair import extract_json_candidate
        cand = extract_json_candidate(resp.content) or resp.content
        return json.loads(cand), resp.content
    except Exception as exc:
        return {"error": str(exc)}, str(exc)

def run_test(p_dir, project_id, model, provider, run_name):
    p_path = Path(p_dir)
    last_run = p_path / "runs" / run_name
    
    manifest_path = last_run / "manuscript_comment_manifest.json"
    source_mode_path = last_run / "source_mode.json"
    
    if not manifest_path.exists() or not source_mode_path.exists():
        print(f"No valid artifacts in run {run_name} for project {project_id}")
        return
        
    source_meta = json.loads(source_mode_path.read_text(encoding="utf-8"))
    doc_path = Path(source_meta["manuscript_source_path"])
    doc = parse_file(doc_path)
    
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    comments = manifest.get("comment_targets", []) or manifest.get("comments", []) or manifest.get("comment_entries", [])
    
    print(f"\n--- Project {project_id} ({run_name}) ---")
    print(f"Original candidate comments count: {len(comments)}")
    
    if not comments:
        return

    test_batch = comments[:10]
    
    print("\nORIGINAL DRAFTS (sample 3):")
    for c in test_batch[:3]:
        print(f"[{c.get('severity')}] {c.get('critique')}")
    
    print("\nRUNNING REFLECTION PASS...")
    refined = _reflection_pass(test_batch, doc, provider, model, [], 300)
    print(f"Refined {len(refined)} comments after reflection.")
    print("Sample refined (3):")
    for c in refined[:3]:
        print(f"[{c.get('severity')}] {c.get('critique')}")
        
    print("\nRUNNING ADJUDICATION PASS...")
    adjudicated = _adjudication_pass(refined, doc, provider, model, 300)
    print(f"Kept {len(adjudicated)} comments after adjudication.")
    print("Sample adjudicated (3):")
    for c in adjudicated[:3]:
        print(f"[{c.get('severity')}] {c.get('critique')}")

    print("\nRUNNING WHOLE RUN AUDIT...")
    recon_path = last_run / "stage_11_reconciliation.json"
    if recon_path.exists():
        recon_payload = json.loads(recon_path.read_text(encoding="utf-8"))
        audit_prompt = (
            "You are an expert manuscript quality auditor. Review the final deep-run output and provide a brutally honest evaluation.\n"
            "Return strict JSON with the following keys:\n"
            "- strongest_comments: list of the most technically grounded and specific comments (extract max 3).\n"
            "- surfaced_issues: list of major issues caught.\n"
            "- missed_issues: what important weaknesses likely still exist that were under-reviewed.\n"
            "- generic_fluff_flag: boolean, whether the review feels padded with low-value fluff.\n"
            "- grounding_quality: string evaluating whether evidence_source and manuscript_quote fields are meaningful.\n"
            "- overall_verdict: string summary of whether this constitutes a serious expert review.\n\n"
            f"RECONCILIATION PAYLOAD:\n{json.dumps(recon_payload)[:8000]}\n\n"
            f"FINAL DOCX COMMENTS (sample):\n{json.dumps(test_batch[:5])}\n"
        )
        audit_payload, _ = _chat_json(provider, model, "You are the whole-run quality auditor. Return strict JSON only.", audit_prompt, 300)
        print("WHOLE RUN AUDIT RESULT:")
        print(json.dumps(audit_payload, indent=2))
    else:
        print("No reconciliation payload found.")

def main():
    cfg = load_config()
    provider = OllamaProvider(cfg.defaults.ollama_base_url)
    model = "qwen3:235b"
    print(f"Testing roles with model: {model}")
    
    run_test("projects/20260325163524_test-existingphactorpaper", "1", model, provider, "20260331_162913_deep_run")
    run_test("projects/20260327051312_miniaturization_d2b", "2", model, provider, "20260331_162914_deep_run")

if __name__ == "__main__":
    main()