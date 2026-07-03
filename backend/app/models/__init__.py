# =============================================================================
# purpose:  Re-exports all ORM models from a single import point.
#           Alembic's env.py imports Base from here to enable autogenerate.
#           All models must be imported here so SQLAlchemy's mapper registry
#           is fully populated before any migration or query runs.
# implements: LMS-SDD-002 §3.1 (app/models/)
#             LMS-DB-003 §1 (schema overview)
# =============================================================================

from app.core.database import Base  # noqa: F401 — Base must be importable from models
from app.models.service import Service  # noqa: F401
from app.models.application_log import ApplicationLog  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401

__all__ = [
    "Base",
    "Service",
    "ApplicationLog",
    "AuditLog",
]
