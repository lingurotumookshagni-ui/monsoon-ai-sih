"""CSV upload route."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..config import MAX_UPLOAD_BYTES
from ..services import datasets
from ..services.uploads import (
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    UploadValidationError,
    parse_and_validate,
    process_upload,
)
from ..services.verification import compare

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/upload-data/template")
def upload_template() -> Dict[str, Any]:
    """Describe the accepted CSV format (used by the dashboard's upload panel)."""
    header = REQUIRED_COLUMNS + [c for c in OPTIONAL_COLUMNS if c != "date"]
    return {
        "required_columns": REQUIRED_COLUMNS,
        "optional_columns": OPTIONAL_COLUMNS,
        "max_bytes": MAX_UPLOAD_BYTES,
        "example_csv": ",".join(header) + "\n"
                       "Kasaragod,12.50,74.99,82,Kerala,103,88,1001,27.5,9.5,255,20,5,7",
        "note": "Missing optional columns are filled with climatological defaults. "
                "Include 'observed_rainfall_mm' if you also want verification scores.",
    }


@router.post("/upload-data")
async def upload_data(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Validate a CSV, run the post-processing pipeline and keep it in session."""
    filename = (file.filename or "upload.csv").lower()
    if not filename.endswith((".csv", ".txt")):
        raise HTTPException(status_code=415,
                            detail="Only .csv files are accepted.")

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")

    try:
        df, summary = parse_and_validate(raw)
    except UploadValidationError as exc:
        # Field-level validation feedback; no internal traces are exposed.
        raise HTTPException(status_code=422,
                            detail={"message": "CSV validation failed.",
                                    "errors": exc.errors})

    try:
        processed = process_upload(df)
    except Exception:
        raise HTTPException(status_code=500,
                            detail="The uploaded data could not be processed.")

    datasets.set_uploaded(processed, {"filename": file.filename, **summary})

    verification_block = None
    if summary["has_observations"]:
        subset = processed.dropna(subset=["observed_rainfall_mm"])
        if len(subset) > 0:
            verification_block = compare(subset)

    return {
        "status": "accepted",
        "filename": file.filename,
        "rows_received": summary["rows_received"],
        "rows_accepted": summary["rows_accepted"],
        "has_observations": summary["has_observations"],
        "warnings": summary["warnings"],
        "columns_detected": summary["columns_detected"],
        "kpis": datasets.summarise(processed),
        "regimes": datasets.regime_summary(processed),
        "verification": verification_block,
        "records": datasets.forecast_records(processed.head(500)),
        "note": "Uploaded data is held in memory for this API process only; "
                "nothing is written to disk or to a database.",
    }


@router.delete("/upload-data")
def clear_upload() -> Dict[str, Any]:
    datasets.clear_uploaded()
    return {"status": "cleared", "active_source": "demo"}


@router.get("/upload-data")
def uploaded_status() -> Dict[str, Any]:
    meta = datasets.get_uploaded_meta()
    return {"has_upload": meta is not None, "meta": meta}
