from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import ezdxf
from ezdxf.entities import DXFEntity

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
MANIFEST_PATH = DATA_DIR / "manifest.json"
SOURCE_PATH = DATA_DIR / "source" / "original.dxf"
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


def source_status() -> dict[str, Any]:
    if not SOURCE_PATH.exists():
        return {"available": False, "path": "data/source/original.dxf"}
    digest = hashlib.sha256()
    with SOURCE_PATH.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "available": True,
        "path": "data/source/original.dxf",
        "size_bytes": SOURCE_PATH.stat().st_size,
        "sha256": digest.hexdigest(),
    }


def sheet_status(sheet: dict[str, Any]) -> dict[str, Any]:
    path = _sheet_path(sheet)
    return {
        **sheet,
        "dxf_available": path.exists(),
        "dxf_path": f"data/sheets/{path.name}",
    }


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
    return [
        {"name": layer, "entity_count": count}
        for layer, count in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    ]


def _base(entity: DXFEntity, inherited_layer: str | None = None) -> dict[str, Any]:
    layer = str(entity.dxf.layer)
    if layer == "0" and inherited_layer:
        layer = inherited_layer
    return {
        "type": entity.dxftype(),
        "layer": layer,
        "handle": getattr(entity.dxf, "handle", None),
    }


def _flatten_curve(entity: DXFEntity, inherited_layer: str | None = None) -> dict[str, Any] | None:
    try:
        points = [_point(p.x, p.y) for p in entity.flattening(distance=8.0)]
    except (AttributeError, TypeError, ValueError, ezdxf.DXFError):
        return None
    if len(points) < 2:
        return None
    return {**_base(entity, inherited_layer), "type": "CURVE", "source_type": entity.dxftype(), "points": points}


def _entity_payloads(
    entity: DXFEntity,
    inherited_layer: str | None = None,
    expand_blocks: bool = True,
    depth: int = 0,
) -> Iterable[dict[str, Any]]:
    kind = entity.dxftype()
    base = _base(entity, inherited_layer)
    layer = base["layer"]

    try:
        if kind == "LINE":
            yield {**base, "start": _point(entity.dxf.start.x, entity.dxf.start.y), "end": _point(entity.dxf.end.x, entity.dxf.end.y)}
            return
        if kind == "LWPOLYLINE":
            points = [_point(x, y) for x, y, *_ in entity.get_points()]
            yield {**base, "points": points, "closed": bool(entity.closed)}
            return
        if kind == "POLYLINE":
            points = [_point(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
            yield {**base, "points": points, "closed": bool(entity.is_closed)}
            return
        if kind == "CIRCLE":
            yield {**base, "center": _point(entity.dxf.center.x, entity.dxf.center.y), "radius": round(float(entity.dxf.radius), 4)}
            return
        if kind == "ARC":
            yield {
                **base,
                "center": _point(entity.dxf.center.x, entity.dxf.center.y),
                "radius": round(float(entity.dxf.radius), 4),
                "start_angle": round(float(entity.dxf.start_angle), 4),
                "end_angle": round(float(entity.dxf.end_angle), 4),
            }
            return
        if kind in {"SPLINE", "ELLIPSE"}:
            payload = _flatten_curve(entity, layer)
            if payload:
                yield payload
            return
        if kind == "TEXT":
            insert = entity.dxf.insert
            yield {**base, "insert": _point(insert.x, insert.y), "text": entity.dxf.text, "height": round(float(entity.dxf.height), 4), "rotation": round(float(entity.dxf.rotation or 0), 4)}
            return
        if kind == "MTEXT":
            insert = entity.dxf.insert
            yield {**base, "insert": _point(insert.x, insert.y), "text": entity.plain_text(), "height": round(float(entity.dxf.char_height), 4), "rotation": round(float(entity.dxf.rotation or 0), 4)}
            return
        if kind == "POINT":
            loc = entity.dxf.location
            yield {**base, "point": _point(loc.x, loc.y)}
            return
        if kind in {"SOLID", "TRACE", "3DFACE"}:
            points = []
            for name in ("vtx0", "vtx1", "vtx2", "vtx3"):
                value = getattr(entity.dxf, name, None)
                if value is not None:
                    points.append(_point(value.x, value.y))
            if points:
                yield {**base, "type": "SOLID", "points": points, "closed": True}
            return
        if kind in {"INSERT", "DIMENSION", "LEADER"} and expand_blocks and depth < 4:
            try:
                for virtual in entity.virtual_entities():
                    yield from _entity_payloads(virtual, inherited_layer=layer, expand_blocks=True, depth=depth + 1)
                return
            except (AttributeError, TypeError, ValueError, ezdxf.DXFError):
                pass
        if kind == "INSERT":
            insert = entity.dxf.insert
            yield {
                **base,
                "name": entity.dxf.name,
                "insert": _point(insert.x, insert.y),
                "rotation": round(float(entity.dxf.rotation or 0), 4),
            }
            return
    except (AttributeError, TypeError, ValueError, ezdxf.DXFError):
        return


def load_entities(
    sheet: dict[str, Any],
    layers: set[str] | None = None,
    limit: int = 25000,
    expand_blocks: bool = True,
) -> dict[str, Any]:
    path = _sheet_path(sheet)
    if not path.exists():
        raise FileNotFoundError(path)
    doc = _read_doc(str(path))
    result: list[dict[str, Any]] = []
    unsupported = 0
    top_level = 0
    for entity in doc.modelspace():
        top_level += 1
        top_layer = str(entity.dxf.layer)
        if layers and top_layer not in layers and top_layer != "0":
            continue
        payloads = list(_entity_payloads(entity, expand_blocks=expand_blocks))
        if not payloads:
            unsupported += 1
            continue
        for payload in payloads:
            if layers and payload["layer"] not in layers:
                continue
            result.append(payload)
            if len(result) >= limit:
                break
        if len(result) >= limit:
            break
    return {
        "sheet_no": sheet["sheet_no"],
        "bounding_box": sheet["bounding_box"],
        "entities": result,
        "returned": len(result),
        "top_level_scanned": top_level,
        "skipped_unsupported": unsupported,
        "truncated": len(result) >= limit,
        "expanded_blocks": expand_blocks,
    }
