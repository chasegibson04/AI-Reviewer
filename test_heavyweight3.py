import json
import logging
from pathlib import Path
from ai_reviewer.config import load_config
from ai_reviewer.models.ollama_provider import OllamaProvider
from ai_reviewer.review.manuscript_annotation import _reflection_pass, _adjudication_pass
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.models.base import ChatRequest

logging.basicConfig(level=logging.INFO)

def run_test(p_dir, project_id, model, provider):
    p_path = Path(p_dir)
    runs = sorted([d for d in (p_path / "runs").iterdir() if d.is_dir()], key=lambda x: x.name)
    if not runs:
        print(f"No runs found for {project_id}")
        return
    last_run = runs[-1]
    
    manifest_path = last_run / "manuscript_comment_manifest.json"
    source_mode_path = last_run / "source_mode.json"
    
    if not manifest_path.exists() or not source_mode_path.exists():
        print(f"No valid artifacts in last run for {project_id} in {last_run}")
        return
        
    source_meta = json.loads(source_mode_path.read_text(encoding="utf-8"))
    doc_path = Path(source_meta["manuscript_source_path"])
    doc = parse_file(doc_path)
    
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    
    # Check both "comments" and "comment_entries"
    comments = manifest.get("comments", []) or manifest.get("comment_entries", [])
    
    print(f"\n--- Project {project_id} ---")
    print(f"Original candidate comments count: {len(comments)}")
    
    if not comments:
        # Check docx_comment_manifest.json
        alt = last_run / "docx_comment_manifest.json"
        if alt.exists():
            manifest = json.loads(alt.read_text(encoding="utf-8"))
            comments = manifest.get("comments", []) or manifest.get("comment_entries", [])
            print(f"Found {len(comments)} comments in docx_comment_manifest.json")

    if not comments:
        # Check any other json files for lists of objects with 'critique'
        for f in last_run.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) > 0 and 'critique' in data[0]:
                    comments = data
                    print(f"Found {len(comments)} comments in {f.name}")
                    break
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict) and 'critique' in v[0]:
                            comments = v
                            print(f"Found {len(comments)} comments in {f.name} under key {k}")
                            break
            except: continue
            if comments: break

    test_batch = comments[:10]
    
    print("\nORIGINAL DRAFTS:")
    for c in test_batch:
        print(f"[{c.get('severity')}] {c.get('critique')}")
    
    if not test_batch:
        return

    print("\nRUNNING REFLECTION PASS...")
    refined = _reflection_pass(test_batch, doc, provider, model, 300)
    print(f"Refined {len(refined)} comments after reflection:")
    for c in refined:
        print(f"[{c.get('severity')}] {c.get('critique')}")
        
    print("\nRUNNING ADJUDICATION PASS...")
    adjudicated = _adjudication_pass(refined, doc, provider, model, 300)
    print(f"Kept {len(adjudicated)} comments after adjudication:")
    for c in adjudicated:
        print(f"[{c.get('severity')}] {c.get('critique')}")


def main():
    cfg = load_config()
    provider = OllamaProvider(cfg.defaults.ollama_base_url)
    model = "qwen3:235b"
    print(f"Testing with model: {model}")
    
    run_test("projects/20260325163524_test-existingphactorpaper", "1", model, provider)
    run_test("projects/20260327051312_miniaturization_d2b", "2", model, provider)

if __name__ == "__main__":
    main()