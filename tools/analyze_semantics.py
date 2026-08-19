from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

import ezdxf

VIEW_RE = re.compile(r"(?:平面图|镜像平面图|立面图|剖面图|剖立面图|详图|一览表|专篇)$")
CODE_RE = re.compile(r"^(?:FM[甲乙丙]?|GM|GSM|DK|LC|BYC|M|ZHM|GSC|GD)[A-Za-z]?-?\d{3,5}[a-z]?$", re.I)
REF_RE = re.compile(r"(?:详见|参见|见).{0,50}(?:详图|图纸|结构|电气|给排水|暖通|环保)")

TITLE_CATEGORY_RULES = [
    (re.compile(r"说明|专篇|做法表|装饰一览表"), "specification"),
    (re.compile(r"门窗一览表"), "schedule"),
    (re.compile(r"吊顶"), "reflected_ceiling_plan"),
    (re.compile(r"平面图"), "plan"),
    (re.compile(r"立面图"), "elevation"),
    (re.compile(r"剖"), "section"),
    (re.compile(r"详图"), "detail"),
]

LAYER_MAP = {
    "WALL": "wall",
    "COLUMN": "column",
    "WINDOW": "window",
    "STAIR": "stair",
    "AXIS": "grid",
    "AXIS_TEXT": "grid_label",
    "ROOF": "roof",
    "HANDRAIL": "handrail",
    "LATRINE": "sanitary",
    "吊顶": "ceiling",
    "PUB_DIM": "dimension",
    "DIM_ELEV": "elevation_mark",
    "DIM_LEAD": "leader",
    "PUB_TEXT": "annotation",
    "PUB_HATCH": "hatch",
}


def classify_title(title: str) -> str:
    for pattern, category in TITLE_CATEGORY_RULES:
        if pattern.search(title):
            return category
    return "other"


def iter_texts(doc):
    for e in doc.modelspace():
        kind = e.dxftype()
        if kind == "TEXT":
            text = e.dxf.text.strip()
            if text:
                yield text, [e.dxf.insert.x, e.dxf.insert.y], "text"
        elif kind == "MTEXT":
            try:
                text = e.plain_text().strip()
            except Exception:
                text = e.text.strip()
            if text:
                yield text, [e.dxf.insert.x, e.dxf.insert.y], "mtext"
        elif kind == "INSERT":
            for a in e.attribs:
                text = a.dxf.text.strip()
                if text:
                    yield text, [e.dxf.insert.x, e.dxf.insert.y], "attribute"


def normalize(text: str) -> str:
    return text.replace("\\P", " ").replace("\n", " ").strip()


def analyze_file(path: Path, title_hint: str = "") -> dict:
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    type_counts = Counter(e.dxftype() for e in msp)
    layer_counts = Counter(getattr(e.dxf, "layer", "0") for e in msp)
    block_counts = Counter(e.dxf.name for e in msp.query("INSERT"))

    views, refs, codes = [], [], []
    for raw, _point, _source in iter_texts(doc):
        text = normalize(raw)
        if VIEW_RE.search(text) and len(text) <= 80:
            views.append(text)
        if REF_RE.search(text):
            refs.append(text)
        compact = text.replace(" ", "")
        if CODE_RE.match(compact):
            codes.append(compact)

    grid_labels = []
    for ins in msp.query("INSERT"):
        if ins.dxf.name == "_AXISO":
            for a in ins.attribs:
                value = a.dxf.text.strip()
                if value:
                    grid_labels.append(value)

    semantic_layers = []
    for layer, count in layer_counts.items():
        semantic = LAYER_MAP.get(layer)
        if semantic:
            semantic_layers.append({"layer": layer, "semantic": semantic, "entity_count": count})

    return {
        "file": path.name,
        "title": title_hint,
        "category": classify_title(title_hint),
        "entity_count": len(msp),
        "entity_types": dict(type_counts),
        "semantic_layers": semantic_layers,
        "top_layers": layer_counts.most_common(20),
        "top_blocks": block_counts.most_common(20),
        "views": list(dict.fromkeys(views)),
        "references": list(dict.fromkeys(refs)),
        "type_codes": list(dict.fromkeys(codes)),
        "grid_labels": list(dict.fromkeys(grid_labels)),
    }


def load_manifest(path: Path | None) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("sheets", data) if isinstance(data, dict) else data
    result = {}
    for row in rows:
        no = row.get("sheet_no") or row.get("sheet")
        title = row.get("sheet_name") or row.get("title") or ""
        if no is not None:
            result[str(no)] = title
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract a first-pass semantic graph from split DXF sheets")
    parser.add_argument("sheet_dir", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/semantic/semantic_graph.json"))
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    sheets, errors = [], []
    for path in sorted(args.sheet_dir.glob("*.dxf")):
        match = re.match(r"J(\d+)", path.name, re.I)
        if not match:
            continue
        sheet_no = f"J{int(match.group(1)):02d}"
        title = manifest.get(sheet_no, "")
        try:
            row = analyze_file(path, title)
            row["sheet_no"] = sheet_no
            sheets.append(row)
        except Exception as exc:
            errors.append({"sheet_no": sheet_no, "file": path.name, "error": str(exc)})

    j05_codes = set()
    for row in sheets:
        if row["sheet_no"] == "J05":
            j05_codes.update(row["type_codes"])

    edges = []
    for row in sheets:
        if row["sheet_no"] == "J05":
            continue
        shared = sorted(j05_codes.intersection(row["type_codes"]))
        if shared:
            edges.append({
                "source": row["sheet_no"],
                "predicate": "USES_TYPE_CODES_FROM",
                "target": "J05",
                "evidence": shared,
            })

    payload = {"sheets": sheets, "edges": edges, "errors": errors}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.output}: {len(sheets)} sheets, {len(edges)} edges, {len(errors)} errors")


if __name__ == "__main__":
    main()
