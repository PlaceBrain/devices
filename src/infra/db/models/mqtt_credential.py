from datetime import datetime

from sqlalchemy import UUID, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.types import IDType

from .base import Base


class MqttCredential(Base):
    __tablename__ = "mqtt_credentials"

    user_id: Mapped[IDType] = mapped_column(UUID, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    allowed_place_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
