from collections.abc import AsyncIterable

import grpc
from dishka import Provider, Scope, provide
from placebrain_contracts.places_pb2_grpc import PlacesServiceStub

from src.core.config import Settings


class PlacesStubProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_places_stub(self, settings: Settings) -> AsyncIterable[PlacesServiceStub]:
        channel = grpc.aio.insecure_channel(settings.places_service_url)
        try:
            yield PlacesServiceStub(channel)
        finally:
            await channel.close()
