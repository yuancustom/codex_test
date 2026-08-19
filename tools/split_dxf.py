from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer

FRAME_NAMES = {"标准图框A0", "标准图框A1", "标准图框A2_1"}


def detect_frames(doc):
    msp = doc.modelspace()
    cache = bbox.Cache()
    frames = []
    for entity in msp.query("INSERT"):
        if entity.dxf.name not in FRAME_NAMES:
            continue
        ext = bbox.extents([entity], cache=cache, fast=True)
        frames.append({"frame_entity": entity, "frame_handle": entity.dxf.handle, "paper_block": entity.dxf.name, "bbox_obj": ext, "rotation": float(entity.dxf.rotation or 0), "scale": float(entity.dxf.xscale or 1)})

    for entity in msp.query("INSERT"):
        name = entity.dxf.name
        if "标准图框" not in name or "tq" not in name.lower():
            continue
        attrs = {a.dxf.tag: (a.dxf.text or "").strip() for a in entity.attribs}
        if not attrs.get("图纸名称"):
            continue
        x, y = entity.dxf.insert.x, entity.dxf.insert.y
        candidates = []
        for frame in frames:
            ext = frame["bbox_obj"]
            if ext.extmin.x - 2 <= x <= ext.extmax.x + 2 and ext.extmin.y - 2 <= y <= ext.extmax.y + 2:
                candidates.append(frame)
        if len(candidates) == 1:
            candidates[0]["title_entity"] = entity
            candidates[0]["attrs"] = attrs

    missing = [f["frame_handle"] for f in frames if "attrs" not in f]
    if missing:
        raise RuntimeError(f"Could not pair title blocks to frames: {missing}")
    return frames, cache


def assign_entities(doc, frames, cache):
    for frame in frames:
        frame["entities"] = []
    unassigned = 0
    for entity in doc.modelspace():
        try:
            ext = bbox.extents([entity], cache=cache, fast=True)
            if not ext.has_data:
                unassigned += 1
                continue
            center = ext.center
            hits = []
            for frame in frames:
                fext = frame["bbox_obj"]
                if fext.extmin.x - 2 <= center.x <= fext.extmax.x + 2 and fext.extmin.y - 2 <= center.y <= fext.extmax.y + 2:
                    hits.append(frame)
            if not hits:
                unassigned += 1
                continue
            hits.sort(key=lambda f: f["bbox_obj"].size.x * f["bbox_obj"].size.y)
            hits[0]["entities"].append(entity)
        except Exception:
            unassigned += 1
    return unassigned


def safe_name(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|#、，（）()\s]+', "_", text).strip("_")[:50]


def export(source: Path, output_dir: Path, manifest_path: Path):
    doc = ezdxf.readfile(source)
    frames, cache = detect_frames(doc)
    unassigned = assign_entities(doc, frames, cache)
    output_dir.mkdir(parents=True, exist_ok=True)
    sheets = []

    for frame in frames:
        attrs = frame["attrs"]
        drawing_no = attrs.get("图号", "")
        title = attrs.get("图纸名称", "")
        if title == "施工图目录":
            continue
        match = re.search(r"J(\d{2})$", drawing_no)
        if not match:
            continue
        sheet_no = f"J{match.group(1)}"
        filename = f"{sheet_no}_{safe_name(title)}.dxf"
        target = output_dir / filename

        new_doc = ezdxf.new(doc.dxfversion)
        try:
            new_doc.header["$INSUNITS"] = doc.header.get("$INSUNITS", 0)
        except Exception:
            pass
        importer = Importer(doc, new_doc)
        importer.import_entities(frame["entities"], new_doc.modelspace())
        importer.finalize()
        new_doc.saveas(target)
        check = ezdxf.readfile(target)
        ext = frame["bbox_obj"]
        sheets.append({"sheet_no": sheet_no, "sheet_name": title, "drawing_no": drawing_no, "ratio": attrs.get("比例", ""), "paper_block": frame["paper_block"], "bounding_box": [round(ext.extmin.x, 3), round(ext.extmin.y, 3), round(ext.extmax.x, 3), round(ext.extmax.y, 3)], "source_entity_count": len(frame["entities"]), "output_file": filename, "output_size_bytes": target.stat().st_size, "reopen_entity_count": len(check.modelspace())})
        print(f"{sheet_no}: {title} -> {filename}")

    sheets.sort(key=lambda s: int(s["sheet_no"][1:]))
    manifest = {"source_file": str(source), "source_size_bytes": source.stat().st_size, "dxf_version": doc.dxfversion, "standard_frame_count": len(frames), "directory_count": len(frames) - len(sheets), "drawing_count": len(sheets), "unassigned_modelspace_entities": unassigned, "sheets": sheets}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done: {len(sheets)} drawings; manifest={manifest_path}")


def main():
    parser = argparse.ArgumentParser(description="Split a multi-sheet architectural DXF by standard drawing frames.")
    parser.add_argument("source", type=Path, nargs="?", default=Path("data/source/original.dxf"))
    parser.add_argument("--output", type=Path, default=Path("data/sheets"))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.json"))
    args = parser.parse_args()
    export(args.source, args.output, args.manifest)


if __name__ == "__main__":
    main()
