from __future__ import annotations

import shutil
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock

import ezdxf
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from tools.split_dxf import export

from .dxf_service import (
    MANIFEST_PATH,
    SHEETS_DIR,
    SOURCE_PATH,
    _read_doc,
    get_sheet_record,
    list_layers,
    load_entities,
    load_manifest,
    sheet_status,
    source_status,
)

MAX_SOURCE_BYTES = 100 * 1024 * 1024
_SPLIT_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dxf-split")
_SPLIT_LOCK = Lock()
_SPLIT_JOB = {
    "state": "idle",
    "processed": 0,
    "total": 26,
    "current_sheet": None,
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}

app = FastAPI(title="DXF Sheet Explorer API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_job(**changes) -> None:
    with _SPLIT_LOCK:
        _SPLIT_JOB.update(changes)


def _run_split_job() -> None:
    _set_job(state="running")

    def progress(processed: int, total: int, record: dict) -> None:
        _set_job(processed=processed, total=total, current_sheet=record["sheet_no"])

    try:
        manifest = export(
            SOURCE_PATH,
            SHEETS_DIR,
            MANIFEST_PATH,
            clean_output=True,
            validate_outputs=False,
            progress_callback=progress,
        )
        _read_doc.cache_clear()
        _set_job(
            state="completed",
            processed=manifest["drawing_count"],
            total=manifest["drawing_count"],
            current_sheet=None,
            finished_at=_utc_now(),
            result={
                "drawing_count": manifest["drawing_count"],
                "standard_frame_count": manifest["standard_frame_count"],
                "directory_count": manifest["directory_count"],
                "unassigned_modelspace_entities": manifest["unassigned_modelspace_entities"],
            },
        )
    except Exception as exc:
        _set_job(state="failed", finished_at=_utc_now(), error=str(exc), current_sheet=None)


@app.get("/api/health")
def health():
    manifest = load_manifest()
    return {"status": "ok", "drawing_count": manifest["drawing_count"], "source": source_status()}


@app.get("/api/source")
def source():
    return source_status()


@app.post("/api/source/upload")
def upload_source(file: UploadFile = File(...)):
    with _SPLIT_LOCK:
        if _SPLIT_JOB["state"] in {"queued", "running"}:
            raise HTTPException(409, "Cannot replace source DXF while splitting is running")

    filename = (file.filename or "").lower()
    if not filename.endswith(".dxf"):
        raise HTTPException(415, "Only .dxf files are accepted")

    SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = SOURCE_PATH.with_suffix(".dxf.uploading")
    written = 0
    try:
        with temp_path.open("wb") as target:
            while chunk := file.file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_SOURCE_BYTES:
                    raise HTTPException(413, "DXF exceeds the 100 MB upload limit")
                target.write(chunk)
        try:
            doc = ezdxf.readfile(temp_path)
        except Exception as exc:
            raise HTTPException(422, f"Invalid DXF: {exc}") from exc
        shutil.move(temp_path, SOURCE_PATH)
        _read_doc.cache_clear()
        _set_job(
            state="idle",
            processed=0,
            total=26,
            current_sheet=None,
            started_at=None,
            finished_at=None,
            result=None,
            error=None,
        )
        return {**source_status(), "dxf_version": doc.dxfversion}
    finally:
        temp_path.unlink(missing_ok=True)
        file.file.close()


@app.post("/api/source/split", status_code=202)
def split_source():
    if not SOURCE_PATH.exists():
        raise HTTPException(409, "Upload a DXF first")
    with _SPLIT_LOCK:
        if _SPLIT_JOB["state"] in {"queued", "running"}:
            return deepcopy(_SPLIT_JOB)
        _SPLIT_JOB.update(
            state="queued",
            processed=0,
            total=26,
            current_sheet=None,
            started_at=_utc_now(),
            finished_at=None,
            result=None,
            error=None,
        )
        snapshot = deepcopy(_SPLIT_JOB)
    _SPLIT_EXECUTOR.submit(_run_split_job)
    return snapshot


@app.get("/api/source/split-status")
def split_status():
    with _SPLIT_LOCK:
        return deepcopy(_SPLIT_JOB)


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
            f"Split DXF for {sheet_no} is not present. Upload the source and call POST /api/source/split.",
        )
