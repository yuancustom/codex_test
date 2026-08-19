from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf.entities import DXFEntity

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"
SHEETS_DIR = DATA_DIR / "sheets"


def _point(x: float, y: float) -> list[float]:
    return [round(float(x), 4), round(float(y), 4)]


def load_manifest() -> dict[str, Any]:
    with MANIFEST_PATH.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def get_sheet_record(sheet_no: str) -> dict[str, Any] | None:
    key = sheet_no.upper()
    for sheet in load_manifest()["sheets"]:
        if sheet["sheet_no"].upper() == key:
            return sheet
    return None


def _sheet_path(sheet: dict[str, Any]) -> Path:
    return SHEETS_DIR / sheet["output_file"]


def sheet_status(sheet: dict[str, Any]) -> dict[str, Any]:
    path = _sheet_path(sheet)
    return {**sheet, "dxf_available": path.exists(), "dxf_path": f"data/sheets/{path.name}"}


@lru_cache(maxsize=32)
def _read_doc(path_string: str):
    return ezdxf.readfile(path_string)


def list_layers(sheet: dict[str, Any]) -> list[dict[str, Any]]:
    path = _sheet_path(sheet)
    if not path.exists():
        return []
    doc = _read_doc(str(path))
    counts: dict[str, int] = {}
    for entity in doc.modelspace():
        layer = str(entity.dxf.layer)
        counts[layer] = counts.get(layer, 0) + 1
    return [{"name": layer, "entity_count": count} for layer, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]


def _entity_payload(entity: DXFEntity) -> dict[str, Any] | None:
    kind = entity.dxftype()
    base: dict[str, Any] = {"type": kind, "layer": str(entity.dxf.layer), "handle": getattr(entity.dxf, "handle", None)}
    try:
        if kind == "LINE":
            return {**base, "start": _point(entity.dxf.start.x, entity.dxf.start.y), "end": _point(entity.dxf.end.x, entity.dxf.end.y)}
        if kind == "LWPOLYLINE":
            return {**base, "points": [_point(x, y) for x, y, *_ in entity.get_points()], "closed": bool(entity.closed)}
        if kind == "POLYLINE":
            return {**base, "points": [_point(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices], "closed": bool(entity.is_closed)}
        if kind == "CIRCLE":
            return {**base, "center": _point(entity.dxf.center.x, entity.dxf.center.y), "radius": round(float(entity.dxf.radius), 4)}
        if kind == "ARC":
            return {**base, "center": _point(entity.dxf.center.x, entity.dxf.center.y), "radius": round(float(entity.dxf.radius), 4), "start_angle": round(float(entity.dxf.start_angle), 4), "end_angle": round(float(entity.dxf.end_angle), 4)}
        if kind == "TEXT":
            insert = entity.dxf.insert
            return {**base, "insert": _point(insert.x, insert.y), "text": entity.dxf.text, "height": round(float(entity.dxf.height), 4)}
        if kind == "MTEXT":
            insert = entity.dxf.insert
            return {**base, "insert": _point(insert.x, insert.y), "text": entity.plain_text(), "height": round(float(entity.dxf.char_height), 4)}
        if kind == "POINT":
            loc = entity.dxf.location
            return {**base, "point": _point(loc.x, loc.y)}
        if kind == "INSERT":
            insert = entity.dxf.insert
            return {**base, "name": entity.dxf.name, "insert": _point(insert.x, insert.y), "rotation": round(float(entity.dxf.rotation or 0), 4)}
    except (AttributeError, TypeError, ValueError):
        return None
    return None


def load_entities(sheet: dict[str, Any], layers: set[str] | None = None, limit: int = 12000) -> dict[str, Any]:
    path = _sheet_path(sheet)
    if not path.exists():
        raise FileNotFoundError(path)
    doc = _read_doc(str(path))
    result: list[dict[str, Any]] = []
    skipped = 0
    for entity in doc.modelspace():
        if layers and str(entity.dxf.layer) not in layers:
            continue
        payload = _entity_payload(entity)
        if payload is None:
            skipped += 1
            continue
        result.append(payload)
        if len(result) >= limit:
            break
    return {"sheet_no": sheet["sheet_no"], "bounding_box": sheet["bounding_box"], "entities": result, "returned": len(result), "skipped_unsupported": skipped, "truncated": len(result) >= limit}
