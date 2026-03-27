# Training Materials

AI-Reviewer supports global lab guidance via local cached training materials.

## Source Folders

`training_materials/` is the source of truth:
- `published_papers/`
- `formatting_color_guides/`
- `external_guides/`
- `other_groups_papers/`
- `in_progress_examples/`

Source files are never moved or deleted by AI-Reviewer.

## Incremental Sync

On startup (when enabled), AI-Reviewer:
1. scans `training_materials/`
2. detects added / changed / removed / unchanged files
3. reprocesses only added/changed files
4. removes deleted files from active guidance
5. refreshes `global_guidance.json`

Manual commands:

```bash
ai-reviewer training status
ai-reviewer training sync
ai-reviewer training rebuild
ai-reviewer training list
ai-reviewer training show <file-id-or-path>
```

## Cache Artifacts

Default cache root: `data/training_cache/`

- `manifest.json`: tracked files + fingerprints + processing state
- `global_guidance.json`: compact aggregated guidance for runtime injection
- `last_sync.json`: most recent sync report
- `files/<id>/parsed.json`: parsed metadata/excerpt
- `files/<id>/takeaways.json`: structured per-file takeaways

## Runtime Injection

Training guidance is injected into all run types by default:
- review
- compare
- evaluation sweep
- project-based workflows
- slack-dev simulation path

Use `--disable-training-guidance` to bypass injection on a run.

## Troubleshooting

- If a file fails to parse, it remains visible in manifest/status with warnings.
- If guidance seems stale, run `ai-reviewer training rebuild`.
- If you deleted a source file but still see old guidance, run `ai-reviewer training sync` and verify `removed` count.

