from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.models.device import Device

from .base import BaseRepository


class DeviceRepository(BaseRepository[Device]):
    def __init__(self, session: AsyncSession):
        super().__init__(Device, session)

    async def delete_by_place(self, place_id: UUID) -> tuple[int, list[str]]:
        result = await self.session.execute(
            delete(Device).where(Device.place_id == place_id).returning(Device.id)
        )
        deleted_ids = result.scalars().all()
        return len(deleted_ids), [str(did) for did in deleted_ids]
