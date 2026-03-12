from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


# ---------------------------------------------------------------------------
# Engine — connection pool configured for a typical single-server deployment.
# pool_pre_ping ensures stale connections are recycled automatically.
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,      # Verify connection health before using it
    pool_size=10,            # Persistent pool connections
    max_overflow=20,         # Extra connections allowed under peak load
    pool_recycle=3600,       # Recycle connections every hour to avoid timeouts
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base — all ORM models inherit from this."""
    pass


def get_db():
    """FastAPI dependency: yields a DB session and guarantees it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
