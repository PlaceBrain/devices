from sqlalchemy.ext.asyncio import AsyncSession

from src.infra.db.models.mqtt_credential import MqttCredential

from .base import BaseRepository


class MqttCredentialRepository(BaseRepository[MqttCredential]):
    def __init__(self, session: AsyncSession):
        super().__init__(MqttCredential, session)
