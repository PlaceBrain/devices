from uuid import UUID

from src.core.exceptions import PermissionDeniedError
from src.core.roles import WRITE_ROLES
from src.services.role_cache import RoleCacheService


async def check_write_permission(
    role_cache: RoleCacheService, user_id: UUID, place_id: UUID
) -> None:
    role = await role_cache.get_role(user_id, place_id)
    if role is None:
        raise PermissionDeniedError("User is not a member of this place")
    if role not in WRITE_ROLES:
        raise PermissionDeniedError("Only owner or admin can perform this action")


async def check_read_permission(
    role_cache: RoleCacheService, user_id: UUID, place_id: UUID
) -> None:
    role = await role_cache.get_role(user_id, place_id)
    if role is None:
        raise PermissionDeniedError("User is not a member of this place")
