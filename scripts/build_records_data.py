#!/usr/bin/env python3
"""
Build records_data.csv from published Google Sheet xlsx export.
Maps each record row to its Drive file ID via embedded hyperlinks.
"""

from __future__ import annotations

import csv
import io
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "records_data.csv"
PUBLISH_ID = (
    "2PACX-1vQTGl81beyGNaaPYWl8BlCcYzYyPHPaws2lo3dOlcQ1Xpl4OBMQg7o3Xp6Z7l0f-w4JLleEODqGT5Lg"
)
RECORDS_GID = "380705787"

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def download_xlsx(gid: str) -> bytes:
    url = (
        f"https://docs.google.com/spreadsheets/d/e/{PUBLISH_ID}/pub"
        f"?output=xlsx&gid={gid}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def col_row(ref: str) -> tuple[int, int]:
    col = 0
    row = 0
    i = 0
    while i < len(ref) and ref[i].isalpha():
        col = col * 26 + (ord(ref[i].upper()) - ord("A") + 1)
        i += 1
    row = int(ref[i:])
    return col, row


def load_relationships(zf: zipfile.ZipFile, rels_path: str) -> dict[str, str]:
    rels: dict[str, str] = {}
    root = ET.fromstring(zf.read(rels_path))
    for rel in root.findall("pr:Relationship", NS):
        rid = rel.attrib.get("Id", "")
        target = rel.attrib.get("Target", "")
        if rid and target:
            rels[rid] = target
    return rels


def extract_row_links(xlsx_bytes: bytes) -> tuple[dict[int, str], dict[int, list[str]]]:
    """Return row->drive_id links and row->cell values."""
    row_links: dict[int, str] = {}
    with zipfile.ZipFile(io.BytesIO(xlsx_bytes)) as zf:
        sheet_path = "xl/worksheets/sheet1.xml"
        rels_path = "xl/worksheets/_rels/sheet1.xml.rels"
        if sheet_path not in zf.namelist():
            raise RuntimeError("sheet1.xml not found in xlsx")

        rels = load_relationships(zf, rels_path) if rels_path in zf.namelist() else {}
        root = ET.fromstring(zf.read(sheet_path))

        hyperlinks = root.find("main:hyperlinks", NS)
        if hyperlinks is not None:
            for hl in hyperlinks.findall("main:hyperlink", NS):
                ref = hl.attrib.get("ref", "")
                if not ref:
                    continue
                _, row = col_row(ref.split(":")[0])
                url = hl.attrib.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}href", ""
                )
                if not url:
                    rid = hl.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
                    url = rels.get(rid, "")
                if "drive.google.com" in url:
                    match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", url) or re.search(
                        r"[?&]id=([a-zA-Z0-9_-]+)", url
                    )
                    if match:
                        row_links[row] = match.group(1)

        # Inline strings for titles / metadata
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in ss_root.findall("main:si", NS):
                texts = [t.text or "" for t in si.findall(".//main:t", NS)]
                shared_strings.append("".join(texts))

        rows_data: dict[int, list[str]] = {}
        sheet_data = root.find("main:sheetData", NS)
        if sheet_data is not None:
            for cell in sheet_data.findall("main:row", NS):
                row_num = int(cell.attrib.get("r", "0"))
                values: list[str] = []
                for c in cell.findall("main:c", NS):
                    col, _ = col_row(c.attrib.get("r", "A1"))
                    cell_type = c.attrib.get("t", "")
                    value = ""
                    if cell_type == "inlineStr":
                        is_elem = c.find("main:is", NS)
                        if is_elem is not None:
                            value = "".join(
                                (t.text or "") for t in is_elem.findall(".//main:t", NS)
                            )
                    else:
                        v = c.find("main:v", NS)
                        if v is not None and v.text is not None:
                            if cell_type == "s":
                                idx = int(v.text)
                                value = shared_strings[idx] if idx < len(shared_strings) else ""
                            else:
                                value = v.text
                    while len(values) < col:
                        values.append("")
                    if len(values) == col - 1:
                        values.append(value)
                    elif len(values) >= col:
                        values[col - 1] = value
                rows_data[row_num] = values

    return row_links, rows_data


def build_records_csv() -> None:
    print("Downloading records tab xlsx...")
    xlsx = download_xlsx(RECORDS_GID)
    row_links, rows_data = extract_row_links(xlsx)

    print(f"  Hyperlinks on {len(row_links)} rows")
    print(f"  Sheet rows parsed: {len(rows_data)}")

    records = []
    for row_num in sorted(rows_data.keys()):
        if row_num < 2:
            continue
        vals = rows_data[row_num]
        media = vals[0].strip() if vals else ""
        title = vals[1].strip() if len(vals) > 1 else ""
        if not media.startswith("Record") or not title:
            continue
        drive_id = row_links.get(row_num, "")
        records.append(
            {
                "sheet_row": row_num,
                "target_rec": len(records) + 1,
                "media_type": media,
                "title": title,
                "drive_id": drive_id,
            }
        )

    print(f"  Record entries: {len(records)}")
    print(f"  With drive_id: {sum(1 for r in records if r['drive_id'])}")

    with open(OUTPUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "",
                "Media Type",
                "Name of Piece",
                "Front Cover",
                "Back Cover",
                "Box #",
                "Number of Songs",
                "Genre",
                "Lyrics By",
                "Music By",
                "Publisher Location",
                "Publisher Company",
                "Publisher",
                "Copyright Date",
                "Misc. / Notes / Other",
                "downloaded_filename",
                "drive_file_id",
            ]
        )
        for rec in records:
            writer.writerow(
                [
                    rec["target_rec"],
                    rec["media_type"],
                    rec["title"],
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    f"NOT DOWNLOADED: {rec['drive_id'][:20]}" if rec["drive_id"] else "",
                    rec["drive_id"],
                ]
            )

    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    build_records_csv()
