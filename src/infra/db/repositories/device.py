from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.models.device import Device

from .base import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    def __init__(self, session: AsyncSession):
        super().__init__(Device, session)
