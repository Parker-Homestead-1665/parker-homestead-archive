#!/usr/bin/env python3
"""
Realign SHE-*.jpg images to match import_master / sheet_data order.

Images were named by Google Drive scrape position, but entries follow Google
Sheet row order. This script uses drive_file_id from sheet_data.csv to find
which existing SHE file contains each piece's image (via MD5 hash), then
renames files so SHE-NNNN matches the correct entry.

Usage:
    python scripts/realign_sheet_music_images.py --dry-run
    python scripts/realign_sheet_music_images.py --apply
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHEET_DATA = ROOT / "sheet_data.csv"
IMAGES_DIR = ROOT / "images"
REPORT_PATH = ROOT / "scripts" / "realignment_report.json"
CACHE_PATH = ROOT / "scripts" / "drive_match_cache.json"


def load_sheet_rows() -> list[dict]:
    rows = []
    with open(SHEET_DATA, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        for i, raw in enumerate(reader):
            if i < 2 or len(raw) < 3:
                continue
            title = raw[2].strip()
            if not title or title == "Name of Piece":
                continue
            row_num = int(raw[0]) if raw[0].strip().isdigit() else len(rows) + 2
            rows.append(
                {
                    "sheet_row": row_num,
                    "target_she": row_num - 1,
                    "title": title,
                    "drive_id": raw[-1].strip(),
                    "media_type": raw[1].strip() if len(raw) > 1 else "",
                }
            )
    return rows


def build_hash_index() -> dict[str, int]:
    index: dict[str, int] = {}
    for path in sorted(IMAGES_DIR.glob("SHE-*.jpg")):
        match = re.search(r"SHE-(\d+)", path.name)
        if not match:
            continue
        digest = hashlib.md5(path.read_bytes()).hexdigest()
        index[digest] = int(match.group(1))
    return index


def load_drive_cache() -> dict[str, int | None]:
    if not CACHE_PATH.exists():
        return {}
    with open(CACHE_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {k: (v if v is not None else None) for k, v in raw.items()}


def save_drive_cache(cache: dict[str, int | None]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f)


def download_drive_file(file_id: str, retries: int = 3) -> bytes:
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to download {file_id}: {last_error}")


def build_realignment_map(
    sheet_rows: list[dict], hash_index: dict[str, int], verbose: bool = True
) -> tuple[dict[int, int], list[dict]]:
    """
    Returns mapping of target_she -> source_she and a list of issues.
    """
    target_to_source: dict[int, int] = {}
    issues: list[dict] = []
    cache = load_drive_cache()
    cached_count = len(cache)

    with_drive = [r for r in sheet_rows if r["drive_id"]]
    total = len(with_drive)
    if cached_count:
        print(f"  Resuming with {cached_count} cached drive lookups")

    for idx, row in enumerate(with_drive, start=1):
        drive_id = row["drive_id"]
        target = row["target_she"]

        if drive_id not in cache:
            if verbose:
                print(f"  [{idx}/{total}] Downloading {drive_id[:12]}... ({row['title'][:40]})")
            try:
                data = download_drive_file(drive_id)
                digest = hashlib.md5(data).hexdigest()
                cache[drive_id] = hash_index.get(digest)
            except Exception as exc:
                cache[drive_id] = None
                issues.append(
                    {
                        "type": "download_failed",
                        "target_she": target,
                        "title": row["title"],
                        "drive_id": drive_id,
                        "error": str(exc),
                    }
                )
            save_drive_cache(cache)
        elif verbose and idx % 50 == 0:
            print(f"  [{idx}/{total}] (cached)")

        source = cache[drive_id]
        if source is None:
            if not any(i.get("drive_id") == drive_id for i in issues):
                issues.append(
                    {
                        "type": "no_matching_image",
                        "target_she": target,
                        "title": row["title"],
                        "drive_id": drive_id,
                    }
                )
            continue

        if source == target:
            target_to_source[target] = target
        else:
            target_to_source[target] = source
            issues.append(
                {
                    "type": "realignment",
                    "target_she": target,
                    "source_she": source,
                    "title": row["title"],
                    "drive_id": drive_id,
                }
            )

    return target_to_source, issues


def complete_mapping(sheet_rows: list[dict], target_to_source: dict[int, int]) -> dict[int, int]:
    """Fill identity mapping for rows without drive_id or unresolved entries."""
    max_she = max(r["target_she"] for r in sheet_rows)
    complete = {n: n for n in range(1, max_she + 1)}
    complete.update(target_to_source)
    return complete


def apply_realignment(
    sheet_rows: list[dict], target_to_source: dict[int, int], dry_run: bool
) -> None:
    """
    Permute SHE files safely via a temp staging directory.
    Always copies from original filenames before replacing anything.
    """
    mapping = complete_mapping(sheet_rows, target_to_source)
    changes = [(t, s) for t, s in mapping.items() if t != s]

    if dry_run:
        print(f"\nDry run: {len(changes)} files would change.")
        for target, source in sorted(changes)[:20]:
            print(f"  SHE-{target:04d}.jpg <- SHE-{source:04d}.jpg")
        if len(changes) > 20:
            print(f"  ... and {len(changes) - 20} more")
        return

    staging = IMAGES_DIR / "_realign_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()

    for target, source in sorted(mapping.items()):
        src_path = IMAGES_DIR / f"SHE-{source:04d}.jpg"
        if not src_path.exists():
            print(f"  WARNING: missing source {src_path.name} for target SHE-{target:04d}")
            continue
        shutil.copy2(src_path, staging / f"SHE-{target:04d}.jpg")

    for path in IMAGES_DIR.glob("SHE-*.jpg"):
        path.unlink()

    for staged in staging.glob("SHE-*.jpg"):
        shutil.move(str(staged), str(IMAGES_DIR / staged.name))

    shutil.rmtree(staging)
    print(f"Realignment applied. {len(list(IMAGES_DIR.glob('SHE-*.jpg')))} SHE images in place.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Realign SHE sheet music images")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    parser.add_argument("--apply", action="store_true", help="Apply file renames")
    parser.add_argument("--report-only", action="store_true", help="Generate report JSON only")
    parser.add_argument(
        "--apply-from-report",
        action="store_true",
        help="Apply realignment using an existing report (skip downloads)",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.apply and not args.report_only and not args.apply_from_report:
        args.dry_run = True

    if not SHEET_DATA.exists():
        print(f"Error: {SHEET_DATA} not found", file=sys.stderr)
        return 1

    print("Loading sheet_data.csv...")
    sheet_rows = load_sheet_rows()
    print(f"  {len(sheet_rows)} sheet music rows")

    if args.apply_from_report:
        if not REPORT_PATH.exists():
            print(f"Error: {REPORT_PATH} not found. Run --report-only first.", file=sys.stderr)
            return 1
        with open(REPORT_PATH, encoding="utf-8") as f:
            report = json.load(f)
        target_to_source = {int(k): v for k, v in report["target_to_source"].items()}
        print(f"Loaded report with {len(target_to_source)} mappings")
        apply_realignment(sheet_rows, target_to_source, dry_run=False)
        download_missing = [
            i for i in report.get("issues", []) if i["type"] == "no_matching_image"
        ]
        if download_missing:
            print(f"\nDownloading {len(download_missing)} images not found in repo...")
            for idx, item in enumerate(download_missing, start=1):
                target = item["target_she"]
                drive_id = item["drive_id"]
                dest = IMAGES_DIR / f"SHE-{target:04d}.jpg"
                print(f"  [{idx}/{len(download_missing)}] SHE-{target:04d} ({item['title'][:40]})")
                data = download_drive_file(drive_id)
                dest.write_bytes(data)
        return 0

    print("Indexing existing SHE images...")
    hash_index = build_hash_index()
    print(f"  {len(hash_index)} images indexed")

    print("Matching drive_file_ids to existing images (this may take several minutes)...")
    target_to_source, issues = build_realignment_map(sheet_rows, hash_index)

    realignments = [i for i in issues if i["type"] == "realignment"]
    already_correct = len(target_to_source) - len(realignments)
    print(f"\nResults:")
    print(f"  Already correct: {already_correct}")
    print(f"  Need realignment: {len(realignments)}")
    print(f"  Other issues: {len(issues) - len(realignments)}")

    report = {
        "target_to_source": {str(k): v for k, v in sorted(target_to_source.items())},
        "issues": issues,
        "summary": {
            "total_sheet_rows": len(sheet_rows),
            "with_drive_id": sum(1 for r in sheet_rows if r["drive_id"]),
            "already_correct": already_correct,
            "realignments_needed": len(realignments),
        },
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport written to {REPORT_PATH}")

    if args.report_only:
        return 0

    if realignments:
        print("\nSample realignments:")
        for item in realignments[:10]:
            print(
                f"  SHE-{item['target_she']:04d} <- SHE-{item['source_she']:04d}  "
                f"({item['title'][:50]})"
            )

    apply_realignment(sheet_rows, target_to_source, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
