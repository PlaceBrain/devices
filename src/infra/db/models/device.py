import enum
from datetime import datetime

from sqlalchemy import UUID, DateTime, Index, String, func
from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy.orm import Mapped, mapped_column

from src.core.types import IDType

from .base import Base


class DeviceStatusEnum(enum.StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


class Device(Base):
    __tablename__ = "devices"

    place_id: Mapped[IDType] = mapped_column(UUID, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DeviceStatusEnum] = mapped_column(
        SQLAlchemyEnum(DeviceStatusEnum), nullable=False, default=DeviceStatusEnum.OFFLINE
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_devices_place_id", "place_id"),)
