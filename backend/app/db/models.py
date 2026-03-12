from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class AnalysisLog(Base):
    """
    Stores every URL analysis result.

    Columns
    -------
    original_url    : The URL submitted by the extension.
    final_url       : The URL after following all redirects.
    is_fraud        : True when the fraud score crosses the detection threshold.
    fraud_score     : Normalised 0-1 score (higher = more suspicious).
    fraud_reasons   : JSON array of human-readable detection reasons.
    redirect_chain  : JSON array of {url, status_code} dicts per hop.
    redirect_count  : Number of redirects in the chain.
    response_time_ms: Wall-clock time to trace the full redirect chain (ms).
    status_code     : Final HTTP status code returned by the destination.
    created_at      : UTC timestamp set by the database on INSERT.
    """

    __tablename__ = "analysis_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_url = Column(String(2048), nullable=False)
    final_url = Column(String(2048), nullable=True)
    is_fraud = Column(Boolean, default=False, nullable=False)
    fraud_score = Column(Float, default=0.0, nullable=False)
    fraud_reasons = Column(Text, nullable=True)   # JSON string
    redirect_chain = Column(Text, nullable=True)  # JSON string
    redirect_count = Column(Integer, default=0, nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    status_code = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Indexes to speed up common query patterns
    __table_args__ = (
        Index("ix_analysis_logs_is_fraud", "is_fraud"),
        Index("ix_analysis_logs_created_at", "created_at"),
        # Prefix index on URL (MySQL requires explicit length for TEXT/VARCHAR > 767 bytes)
        Index("ix_analysis_logs_original_url", "original_url", mysql_length=255),
    )
