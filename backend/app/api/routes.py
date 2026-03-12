import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import AnalysisLog
from app.services.fraud_detector import FraudDetector
from app.services.url_tracer import URLTracer

router = APIRouter()
logger = logging.getLogger(__name__)

# Module-level singletons — created once, reused across requests
tracer = URLTracer(
    max_redirects=settings.MAX_REDIRECTS,
    timeout=settings.REQUEST_TIMEOUT,
)
detector = FraudDetector()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("URL cannot be empty")
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")
        if len(v) > 2048:
            raise ValueError("URL exceeds maximum length of 2048 characters")
        return v


class RedirectHop(BaseModel):
    url: str
    status_code: Optional[int] = None
    error: Optional[str] = None


class AnalysisResponse(BaseModel):
    id: Optional[int] = None
    original_url: str
    final_url: Optional[str] = None
    is_fraud: bool
    fraud_score: float
    fraud_reasons: list[str]
    redirect_chain: list[dict]
    redirect_count: int
    response_time_ms: Optional[int] = None
    status_code: Optional[int] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalysisResponse, summary="Analyse a URL for fraud")
async def analyze_url(request: AnalyzeRequest, db: Session = Depends(get_db)):
    """
    Three-step pipeline:

    1. **Trace** — follow HTTP/HTTPS redirects and record the chain.
    2. **Detect** — run heuristics against the origin URL, final URL, and chain.
    3. **Persist** — save the result to MySQL and return it to the caller.

    A database failure will **not** abort the response; the caller still
    receives the analysis result even if the log write fails.
    """
    logger.info("Received analysis request for: %s", request.url)

    # ── Step 1: Redirect tracing ──────────────────────────────────────────
    try:
        trace = await tracer.trace(request.url)
    except Exception as exc:
        logger.error("Tracing failed for %s: %s", request.url, exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"URL tracing failed: {exc}")

    # ── Step 2: Fraud detection ───────────────────────────────────────────
    try:
        fraud = detector.analyze(trace)
    except Exception as exc:
        logger.error("Fraud detection failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fraud detection failed: {exc}")

    # ── Step 3: Persist to database ───────────────────────────────────────
    log_id: Optional[int] = None
    try:
        entry = AnalysisLog(
            original_url=request.url[:2048],
            final_url=(trace.get("final_url") or "")[:2048],
            is_fraud=fraud["is_fraud"],
            fraud_score=fraud["fraud_score"],
            fraud_reasons=json.dumps(fraud["fraud_reasons"]),
            redirect_chain=json.dumps(trace.get("redirect_chain", [])),
            redirect_count=trace.get("redirect_count", 0),
            response_time_ms=trace.get("response_time_ms"),
            status_code=trace.get("status_code"),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        log_id = entry.id
        logger.info("Saved analysis log id=%d for url=%s", log_id, request.url)
    except Exception as exc:
        db.rollback()
        logger.error("Database write failed (analysis still returned): %s", exc, exc_info=True)

    return AnalysisResponse(
        id=log_id,
        original_url=request.url,
        final_url=trace.get("final_url"),
        is_fraud=fraud["is_fraud"],
        fraud_score=fraud["fraud_score"],
        fraud_reasons=fraud["fraud_reasons"],
        redirect_chain=trace.get("redirect_chain", []),
        redirect_count=trace.get("redirect_count", 0),
        response_time_ms=trace.get("response_time_ms"),
        status_code=trace.get("status_code"),
    )


@router.get("/logs", response_model=list[AnalysisResponse], summary="Retrieve analysis history")
def get_logs(
    limit: int = 50,
    offset: int = 0,
    fraud_only: bool = False,
    db: Session = Depends(get_db),
):
    """
    Return stored analysis logs, newest first.

    Query parameters
    ----------------
    limit      : Maximum records to return (capped at 200).
    offset     : Pagination offset.
    fraud_only : When true, return only records flagged as fraud.
    """
    limit = min(max(limit, 1), 200)
    query = db.query(AnalysisLog)
    if fraud_only:
        query = query.filter(AnalysisLog.is_fraud == True)  # noqa: E712
    rows = (
        query.order_by(AnalysisLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        AnalysisResponse(
            id=row.id,
            original_url=row.original_url,
            final_url=row.final_url,
            is_fraud=row.is_fraud,
            fraud_score=row.fraud_score,
            fraud_reasons=json.loads(row.fraud_reasons or "[]"),
            redirect_chain=json.loads(row.redirect_chain or "[]"),
            redirect_count=row.redirect_count,
            response_time_ms=row.response_time_ms,
            status_code=row.status_code,
        )
        for row in rows
    ]


@router.get("/health", summary="Health check")
def health_check():
    """Returns 200 OK when the service is running."""
    return {"status": "ok", "service": "fraud-detection-api"}
