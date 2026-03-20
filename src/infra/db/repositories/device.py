from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.models.device import Device

from .base import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    def __init__(self, session: AsyncSession):
        super().__init__(Device, session)

    async def delete_by_place(self, place_id: UUID) -> tuple[int, list[str]]:
        ids_result = await self.session.scalars(
            select(Device.id).where(Device.place_id == place_id)
        )
        device_ids = [str(did) for did in ids_result.all()]
        if not device_ids:
            return 0, []
        result = await self.session.execute(delete(Device).where(Device.place_id == place_id))
        return result.rowcount, device_ids
