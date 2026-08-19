from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .dxf_service import (
    get_sheet_record,
    list_layers,
    load_entities,
    load_manifest,
    sheet_status,
    source_status,
)

app = FastAPI(title="DXF Sheet Explorer API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    manifest = load_manifest()
    return {"status": "ok", "drawing_count": manifest["drawing_count"], "source": source_status()}


@app.get("/api/source")
def source():
    return source_status()


@app.get("/api/sheets")
def sheets():
    manifest = load_manifest()
    return {
        "drawing_count": manifest["drawing_count"],
        "standard_frame_count": manifest["standard_frame_count"],
        "sheets": [sheet_status(sheet) for sheet in manifest["sheets"]],
    }


@app.get("/api/sheets/{sheet_no}")
def sheet(sheet_no: str):
    record = get_sheet_record(sheet_no)
    if not record:
        raise HTTPException(404, f"Unknown sheet: {sheet_no}")
    return {**sheet_status(record), "layers": list_layers(record)}


@app.get("/api/sheets/{sheet_no}/entities")
def entities(
    sheet_no: str,
    layer: list[str] | None = Query(default=None),
    limit: int = Query(default=25000, ge=1, le=100000),
    expand_blocks: bool = Query(default=True),
):
    record = get_sheet_record(sheet_no)
    if not record:
        raise HTTPException(404, f"Unknown sheet: {sheet_no}")
    try:
        return load_entities(record, set(layer) if layer else None, limit=limit, expand_blocks=expand_blocks)
    except FileNotFoundError:
        raise HTTPException(
            409,
            f"Split DXF for {sheet_no} is not present. Run: python tools/split_dxf.py data/source/original.dxf",
        )
