from uuid import UUID

from placebrain_contracts import places_pb2 as places_pb
from placebrain_contracts.places_pb2_grpc import PlacesServiceStub

from src.core.exceptions import PermissionDeniedError
from src.core.roles import WRITE_ROLES


async def check_write_permission(
    places_stub: PlacesServiceStub, user_id: UUID, place_id: UUID
) -> None:
    response = await places_stub.GetPlace(
        places_pb.GetPlaceRequest(user_id=str(user_id), place_id=str(place_id))
    )
    if response.user_role not in WRITE_ROLES:
        raise PermissionDeniedError("Only owner or admin can perform this action")


async def check_read_permission(
    places_stub: PlacesServiceStub, user_id: UUID, place_id: UUID
) -> None:
    await places_stub.GetPlace(
        places_pb.GetPlaceRequest(user_id=str(user_id), place_id=str(place_id))
    )
