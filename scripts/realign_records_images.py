#!/usr/bin/env python3
"""
Realign REC-*.jpg images to match import_master / records source order.

Works like realign_sheet_music_images.py but for the records collection.
Requires drive_file_id values (same bridge used for sheet music).

Supported input files (first match wins):
  1. records_data.csv  - CSV with drive_file_id column (preferred, like sheet_data.csv)
  2. records.txt       - tab export; only works if drive_file_id is in the last column

Usage:
    python scripts/realign_records_images.py --dry-run
    python scripts/realign_records_images.py --report-only
    python scripts/realign_records_images.py --apply-from-report
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
RECORDS_CSV = ROOT / "records_data.csv"
RECORDS_TXT = ROOT / "records.txt"
IMAGES_DIR = ROOT / "images"
REPORT_PATH = ROOT / "scripts" / "records_realignment_report.json"
CACHE_PATH = ROOT / "scripts" / "records_drive_match_cache.json"


def load_from_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        all_rows = list(reader)

    # Skip blank / header rows (same pattern as sheet_data.csv)
    for i, raw in enumerate(all_rows):
        if len(raw) < 3:
            continue
        title = raw[2].strip() if len(raw) > 2 else ""
        if not title or title in ("Name of Piece", "Media Type (Sheet, Book, or Records)"):
            continue
        rec_num = int(raw[0]) if raw[0].strip().isdigit() else len(rows) + 1
        media = raw[1].strip() if len(raw) > 1 else ""
        if media and media not in ("Record", "Records"):
            continue
        rows.append(
            {
                "sheet_row": rec_num,
                "target_rec": rec_num,
                "title": title,
                "drive_id": raw[-1].strip(),
            }
        )
    return rows


def load_from_txt(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f]

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.isdigit():
            row_num = int(line)
            if i + 1 < len(lines):
                parts = [p.strip() for p in lines[i + 1].split("\t")]
                title = ""
                drive_id = parts[-1] if parts else ""
                for j, part in enumerate(parts):
                    if part == "Record" and j + 1 < len(parts):
                        title = parts[j + 1].strip()
                        break
                # Heuristic: drive IDs are long alphanumeric strings
                if drive_id and not re.fullmatch(r"[1-9][A-Za-z0-9_-]{20,}", drive_id):
                    drive_id = ""
                if title:
                    rows.append(
                        {
                            "sheet_row": row_num,
                            "target_rec": len(rows) + 1,
                            "title": title,
                            "drive_id": drive_id,
                        }
                    )
            i += 2
        else:
            i += 1
    return rows


def load_record_rows() -> list[dict]:
    if RECORDS_CSV.exists():
        print(f"Loading {RECORDS_CSV.name}...")
        return load_from_csv(RECORDS_CSV)
    if RECORDS_TXT.exists():
        print(f"Loading {RECORDS_TXT.name}...")
        return load_from_txt(RECORDS_TXT)
    raise FileNotFoundError(
        "No records source file found. Add records_data.csv (with drive_file_id) "
        "or records.txt to the repo root."
    )


def build_hash_index() -> dict[str, int]:
    index: dict[str, int] = {}
    for path in sorted(IMAGES_DIR.glob("REC-*.jpg")):
        match = re.search(r"REC-(\d+)", path.name)
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
    record_rows: list[dict], hash_index: dict[str, int], verbose: bool = True
) -> tuple[dict[int, int], list[dict]]:
    target_to_source: dict[int, int] = {}
    issues: list[dict] = []
    cache = load_drive_cache()

    with_drive = [r for r in record_rows if r["drive_id"]]
    if not with_drive:
        raise ValueError(
            "No drive_file_id values found in the records source file.\n"
            "Export your Records Google Sheet tab the same way as sheet_data.csv "
            "(with downloaded_filename and drive_file_id columns) and save as "
            "records_data.csv in the repo root."
        )

    total = len(with_drive)
    if cache:
        print(f"  Resuming with {len(cache)} cached drive lookups")

    for idx, row in enumerate(with_drive, start=1):
        drive_id = row["drive_id"]
        target = row["target_rec"]

        if drive_id not in cache:
            if verbose:
                print(f"  [{idx}/{total}] {drive_id[:12]}... ({row['title'][:40]})")
            try:
                data = download_drive_file(drive_id)
                digest = hashlib.md5(data).hexdigest()
                cache[drive_id] = hash_index.get(digest)
            except Exception as exc:
                cache[drive_id] = None
                issues.append(
                    {
                        "type": "download_failed",
                        "target_rec": target,
                        "title": row["title"],
                        "drive_id": drive_id,
                        "error": str(exc),
                    }
                )
            save_drive_cache(cache)

        source = cache[drive_id]
        if source is None:
            if not any(i.get("drive_id") == drive_id for i in issues):
                issues.append(
                    {
                        "type": "no_matching_image",
                        "target_rec": target,
                        "sheet_row": row["sheet_row"],
                        "title": row["title"],
                        "drive_id": drive_id,
                    }
                )
            continue

        target_to_source[target] = source
        if source != target:
            issues.append(
                {
                    "type": "realignment",
                    "target_rec": target,
                    "source_rec": source,
                    "title": row["title"],
                    "drive_id": drive_id,
                }
            )

    return target_to_source, issues


def complete_mapping(record_rows: list[dict], target_to_source: dict[int, int]) -> dict[int, int]:
    max_rec = max(r["target_rec"] for r in record_rows)
    complete = {n: n for n in range(1, max_rec + 1)}
    complete.update(target_to_source)
    return complete


def apply_realignment(
    record_rows: list[dict], target_to_source: dict[int, int], dry_run: bool
) -> None:
    mapping = complete_mapping(record_rows, target_to_source)
    changes = [(t, s) for t, s in mapping.items() if t != s]

    if dry_run:
        print(f"\nDry run: {len(changes)} files would change.")
        for target, source in sorted(changes)[:20]:
            print(f"  REC-{target:04d}.jpg <- REC-{source:04d}.jpg")
        if len(changes) > 20:
            print(f"  ... and {len(changes) - 20} more")
        return

    staging = IMAGES_DIR / "_rec_realign_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()

    for target, source in sorted(mapping.items()):
        src_path = IMAGES_DIR / f"REC-{source:04d}.jpg"
        if not src_path.exists():
            print(f"  WARNING: missing {src_path.name} for REC-{target:04d}")
            continue
        shutil.copy2(src_path, staging / f"REC-{target:04d}.jpg")

    for path in IMAGES_DIR.glob("REC-*.jpg"):
        path.unlink()

    for staged in staging.glob("REC-*.jpg"):
        shutil.move(str(staged), str(IMAGES_DIR / staged.name))

    shutil.rmtree(staging)
    print(f"Realignment applied. {len(list(IMAGES_DIR.glob('REC-*.jpg')))} REC images in place.")


def validate_titles(record_rows: list[dict]) -> None:
    import_master = ROOT / "import_master.csv"
    masters = []
    with open(import_master, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("Imported ID", "").startswith("REC-"):
                masters.append(row.get("Dublin Core:Title", "").strip())

    mismatches = 0
    for rec_row, master_title in zip(record_rows, masters):
        if rec_row["title"] != master_title:
            mismatches += 1
    print(f"  Title check vs import_master: {len(record_rows)} records, {mismatches} mismatches")


def main() -> int:
    parser = argparse.ArgumentParser(description="Realign REC record images")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--apply-from-report", action="store_true")
    parser.add_argument(
        "--apply-download",
        action="store_true",
        help="Download correct images from Drive and overwrite REC files",
    )
    args = parser.parse_args()

    if (
        not args.dry_run
        and not args.report_only
        and not args.apply_from_report
        and not args.apply_download
    ):
        args.dry_run = True

    try:
        record_rows = load_record_rows()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"  {len(record_rows)} record rows")
    validate_titles(record_rows)

    if args.apply_from_report:
        if not REPORT_PATH.exists():
            print(f"Error: {REPORT_PATH} not found", file=sys.stderr)
            return 1
        with open(REPORT_PATH, encoding="utf-8") as f:
            report = json.load(f)
        target_to_source = {int(k): v for k, v in report["target_to_source"].items()}
        if target_to_source:
            apply_realignment(record_rows, target_to_source, dry_run=False)
        download_items = [
            i
            for i in report.get("issues", [])
            if i["type"] in ("no_matching_image", "download_failed")
        ]
        if download_items:
            print(f"\nDownloading {len(download_items)} images from Drive...")
            for idx, item in enumerate(download_items, start=1):
                target = item["target_rec"]
                if target < 1:
                    target = item.get("sheet_row", target + 1) - 1
                dest = IMAGES_DIR / f"REC-{target:04d}.jpg"
                print(f"  [{idx}/{len(download_items)}] REC-{target:04d} ({item['title'][:40]})")
                dest.write_bytes(download_drive_file(item["drive_id"]))
        return 0

    if args.apply_download:
        with_drive = [r for r in record_rows if r["drive_id"]]
        print(f"Downloading {len(with_drive)} record images from Drive...")
        for idx, row in enumerate(with_drive, start=1):
            target = row["target_rec"]
            dest = IMAGES_DIR / f"REC-{target:04d}.jpg"
            print(f"  [{idx}/{len(with_drive)}] REC-{target:04d} ({row['title'][:40]})")
            dest.write_bytes(download_drive_file(row["drive_id"]))
        print("Done.")
        return 0

    with_drive = sum(1 for r in record_rows if r["drive_id"])
    print(f"  {with_drive} rows with drive_file_id")
    if with_drive == 0:
        print(
            "\nCannot realign images without drive_file_id values.\n"
            "Your records.txt has correct titles/metadata, but is missing the Drive\n"
            "file ID column that sheet_data.csv had. Please export the Records tab\n"
            "from Google Sheets the same way (with drive_file_id column) and save as\n"
            "records_data.csv in the repo root, then re-run this script."
        )
        return 1

    print("Indexing REC images...")
    hash_index = build_hash_index()
    print(f"  {len(hash_index)} images indexed")

    print("Matching drive_file_ids to images...")
    target_to_source, issues = build_realignment_map(record_rows, hash_index)

    realignments = [i for i in issues if i["type"] == "realignment"]
    print(f"\nResults:")
    print(f"  Mapped: {len(target_to_source)}")
    print(f"  Realignments needed: {len(realignments)}")
    print(f"  Other issues: {len(issues) - len(realignments)}")

    report = {
        "target_to_source": {str(k): v for k, v in sorted(target_to_source.items())},
        "issues": issues,
        "summary": {
            "total_rows": len(record_rows),
            "with_drive_id": with_drive,
            "realignments_needed": len(realignments),
        },
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report: {REPORT_PATH}")

    if args.report_only:
        return 0

    apply_realignment(record_rows, target_to_source, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
