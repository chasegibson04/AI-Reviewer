from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ai_reviewer.config import ReviewerConfig
from ai_reviewer.ingest.loaders import parse_file
from ai_reviewer.training.injector import GuidanceInjection, build_guidance_injection
from ai_reviewer.paths import REPO_ROOT
from ai_reviewer.training.manifest import load_manifest, save_manifest
from ai_reviewer.training.scanner import ScannedTrainingFile, diff_manifest, ensure_training_tree, scan_training_files
from ai_reviewer.training.schema import GlobalGuidance, TrainingFileRecord
from ai_reviewer.training.takeaways import extract_takeaways


@dataclass
class TrainingSyncReport:
    added: int
    changed: int
    removed: int
    unchanged: int
    processed: int
    failed: int
    active_files: int
    by_category: dict[str, int]
    warnings: list[str]


class TrainingCacheManager:
    def __init__(self, source_root: Path, cache_root: Path, logger=None):
        self.source_root = source_root
        self.cache_root = cache_root
        self.logger = logger
        self.manifest_path = cache_root / "manifest.json"
        self.global_guidance_path = cache_root / "global_guidance.json"
        self.files_root = cache_root / "files"
        self.last_sync_path = cache_root / "last_sync.json"
        ensure_training_tree(self.source_root)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.files_root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_config(cls, config: ReviewerConfig, logger=None) -> "TrainingCacheManager":
        source_root = Path(config.training.source_root)
        cache_root = Path(config.training.cache_root)
        if not source_root.is_absolute():
            source_root = REPO_ROOT / source_root
        if not cache_root.is_absolute():
            cache_root = REPO_ROOT / cache_root
        return cls(source_root, cache_root, logger=logger)

    def _log(self, msg: str, *args):
        if self.logger:
            self.logger.info(msg, *args)

    def _record_for(self, source: ScannedTrainingFile, parse_status: str, digest_status: str, warnings: list[str], parsed_metadata_file: str | None, takeaway_file: str | None, error: str | None = None) -> TrainingFileRecord:
        file_id = source.fingerprint[:16]
        return TrainingFileRecord(
            file_id=file_id,
            relative_path=source.relative_path,
            absolute_path=source.absolute_path,
            category=source.category,
            fingerprint=source.fingerprint,
            size_bytes=source.size_bytes,
            modified_timestamp=source.modified_timestamp,
            parse_status=parse_status,  # type: ignore[arg-type]
            digest_status=digest_status,  # type: ignore[arg-type]
            warnings=warnings,
            parsed_metadata_file=parsed_metadata_file,
            takeaway_file=takeaway_file,
            included_in_guidance=parse_status == "ok" and digest_status == "ok",
            error=error,
        )

    def _file_cache_dir(self, file_id: str) -> Path:
        d = self.files_root / file_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def sync(self, force_rebuild: bool = False) -> TrainingSyncReport:
        manifest = load_manifest(self.manifest_path, self.source_root)
        scanned = scan_training_files(self.source_root)
        previous = {rel: rec.fingerprint for rel, rec in manifest.files.items()}
        added, changed, removed, unchanged = diff_manifest(previous, scanned)
        to_process = sorted(scanned.keys()) if force_rebuild else sorted(set(added + changed))
        warnings: list[str] = []
        failed = 0
        processed = 0

        for rel in removed:
            rec = manifest.files.pop(rel, None)
            if rec and rec.file_id:
                d = self.files_root / rec.file_id
                if d.exists():
                    for child in d.glob("*"):
                        child.unlink(missing_ok=True)
                    d.rmdir()

        for rel in to_process:
            source = scanned[rel]
            processed += 1
            parsed_metadata_file = None
            takeaway_file = None
            parse_warnings: list[str] = []
            try:
                doc = parse_file(Path(source.absolute_path))
                parse_warnings = list(doc.parse_warnings)
                cache_dir = self._file_cache_dir(source.fingerprint[:16])

                parsed_payload = {
                    "source_path": str(doc.source_path),
                    "document_type": doc.document_type,
                    "parse_engine": doc.parse_engine,
                    "file_size_bytes": doc.file_size_bytes,
                    "cleaned_text_length": len(doc.cleaned_text),
                    "headings": doc.headings[:40],
                    "page_count": doc.page_count,
                    "parse_warnings": doc.parse_warnings,
                    "cleaned_text_excerpt": doc.cleaned_text[:12000],
                }
                parsed_metadata_file = str((cache_dir / "parsed.json").relative_to(self.cache_root))
                (cache_dir / "parsed.json").write_text(json.dumps(parsed_payload, indent=2), encoding="utf-8")

                takeaways = extract_takeaways(
                    file_id=source.fingerprint[:16],
                    source_path=source.relative_path,
                    category=source.category,
                    doc=doc,
                )
                takeaway_file = str((cache_dir / "takeaways.json").relative_to(self.cache_root))
                (cache_dir / "takeaways.json").write_text(takeaways.model_dump_json(indent=2), encoding="utf-8")

                manifest.files[rel] = self._record_for(source, "ok", "ok", parse_warnings, parsed_metadata_file, takeaway_file)
            except Exception as exc:
                failed += 1
                warnings.append(f"{rel}: {exc}")
                manifest.files[rel] = self._record_for(
                    source=source,
                    parse_status="failed",
                    digest_status="failed",
                    warnings=parse_warnings + [str(exc)],
                    parsed_metadata_file=parsed_metadata_file,
                    takeaway_file=takeaway_file,
                    error=str(exc),
                )

        global_guidance = self._rebuild_global_guidance(manifest)
        save_manifest(self.manifest_path, manifest)
        self.global_guidance_path.write_text(global_guidance.model_dump_json(indent=2), encoding="utf-8")

        report = TrainingSyncReport(
            added=len(added),
            changed=len(changed),
            removed=len(removed),
            unchanged=len(unchanged),
            processed=processed,
            failed=failed,
            active_files=global_guidance.active_file_count,
            by_category=global_guidance.active_by_category,
            warnings=warnings + global_guidance.warnings,
        )
        self.last_sync_path.write_text(
            json.dumps(
                {
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                    "report": report.__dict__,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self._log(
            "training_sync added=%s changed=%s removed=%s unchanged=%s failed=%s active=%s",
            report.added,
            report.changed,
            report.removed,
            report.unchanged,
            report.failed,
            report.active_files,
        )
        return report

    def _rebuild_global_guidance(self, manifest) -> GlobalGuidance:
        style: list[str] = []
        formatting: list[str] = []
        language: list[str] = []
        tone: list[str] = []
        by_category: dict[str, int] = {}
        category_guidance: dict[str, list[str]] = {}
        warnings: list[str] = []
        source_files: list[str] = []

        for rel, record in manifest.files.items():
            if not record.included_in_guidance or record.parse_status != "ok" or not record.takeaway_file:
                continue
            t_path = self.cache_root / record.takeaway_file
            if not t_path.exists():
                warnings.append(f"Missing takeaway artifact: {record.takeaway_file}")
                continue
            payload = json.loads(t_path.read_text(encoding="utf-8"))
            style.extend(payload.get("style_guidance", []))
            formatting.extend(payload.get("formatting_layout_guidance", []))
            language.extend(payload.get("language_grammar_guidance", []))
            tone.extend(payload.get("reviewer_tone_guidance", []))
            cat = record.category
            by_category[cat] = by_category.get(cat, 0) + 1
            cat_bullets = payload.get("notable_conventions", []) + payload.get("style_guidance", [])[:2]
            category_guidance.setdefault(cat, []).extend(cat_bullets)
            source_files.append(rel)

        def dedupe(items: list[str], max_items: int = 24) -> list[str]:
            seen = set()
            out = []
            for item in items:
                key = item.strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                out.append(item.strip())
                if len(out) >= max_items:
                    break
            return out

        global_summary = "Lab-wide guidance synthesized from curated local training materials."
        if source_files:
            global_summary += f" Active sources: {len(source_files)}."
        else:
            global_summary += " No active sources."

        return GlobalGuidance(
            active_file_count=len(source_files),
            active_by_category=by_category,
            global_summary=global_summary,
            style_guidance=dedupe(style),
            formatting_guidance=dedupe(formatting),
            language_guidance=dedupe(language),
            reviewer_tone_guidance=dedupe(tone),
            category_guidance={k: dedupe(v, max_items=10) for k, v in category_guidance.items()},
            warnings=warnings,
            source_files=sorted(source_files),
        )

    def load_global_guidance(self) -> GlobalGuidance:
        if not self.global_guidance_path.exists():
            return GlobalGuidance()
        return GlobalGuidance.model_validate_json(self.global_guidance_path.read_text(encoding="utf-8"))

    def status(self) -> dict:
        manifest = load_manifest(self.manifest_path, self.source_root)
        guidance = self.load_global_guidance()
        per_category: dict[str, int] = {}
        failures = 0
        for record in manifest.files.values():
            per_category[record.category] = per_category.get(record.category, 0) + 1
            if record.parse_status != "ok":
                failures += 1
        last_sync = {}
        if self.last_sync_path.exists():
            last_sync = json.loads(self.last_sync_path.read_text(encoding="utf-8"))
        return {
            "source_root": str(self.source_root),
            "cache_root": str(self.cache_root),
            "tracked_files": len(manifest.files),
            "active_guidance_files": guidance.active_file_count,
            "files_by_category": per_category,
            "parse_failures": failures,
            "last_sync": last_sync.get("synced_at"),
        }

    def list_records(self) -> list[TrainingFileRecord]:
        manifest = load_manifest(self.manifest_path, self.source_root)
        return sorted(manifest.files.values(), key=lambda r: r.relative_path)

    def show_record(self, key: str) -> dict:
        manifest = load_manifest(self.manifest_path, self.source_root)
        for rel, rec in manifest.files.items():
            if key in {rel, rec.file_id, Path(rel).name}:
                data = rec.model_dump()
                if rec.takeaway_file:
                    t_path = self.cache_root / rec.takeaway_file
                    if t_path.exists():
                        data["takeaways"] = json.loads(t_path.read_text(encoding="utf-8"))
                return data
        raise KeyError(f"Training record not found: {key}")

    def injection_for_profile(self, profile_key: str, max_chars: int) -> GuidanceInjection:
        guidance = self.load_global_guidance()
        return build_guidance_injection(guidance, profile_key=profile_key, max_chars=max_chars)
