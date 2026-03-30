# Training Materials

AI-Reviewer supports a local cached training-guidance layer for style and standards pressure.

## Source Of Truth

`training_materials/` is the source tree. Files are not moved or deleted by AI-Reviewer.

Typical folders:
- `published_papers/`
- `formatting_color_guides/`
- `external_guides/`
- `other_groups_papers/`
- `in_progress_examples/`

## Cache Artifacts

Default cache root:
- `data/training_cache/`

Important files:
- `manifest.json`
- `global_guidance.json`
- `last_sync.json`
- `files/<id>/parsed.json`
- `files/<id>/takeaways.json`

## Runtime Behavior

When enabled, the cache can sync on launcher start and before review workflows.
Guidance is injected into:
- `review`
- `deep-run`
- `compare`
- `evaluate-paper`

This guidance is style/constraint context only. It is not supposed to replace manuscript-grounded critique.

## Commands

```powershell
ai-reviewer training status
ai-reviewer training sync
ai-reviewer training rebuild
ai-reviewer training list
ai-reviewer training show <file-id-or-path>
```

## Troubleshooting

- stale guidance -> run `ai-reviewer training rebuild`
- removed source file still appears -> run `ai-reviewer training sync`
- parse failure -> inspect cache manifest and file-level warnings
