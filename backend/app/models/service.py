from datetime import datetime

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.time import utcnow
from app.models.types import Timestamp


class Service(Base):
    """Registry of producers allowed to ingest logs. Disabled services are rejected."""

    __tablename__ = "services"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(Timestamp, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        Timestamp, nullable=False, default=utcnow, onupdate=utcnow
    )

    def __repr__(self) -> str:
        return f"<Service {self.id!r} active={self.is_active}>"
