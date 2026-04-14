class DevicesServiceError(Exception):
    """Base for all devices domain exceptions."""


class NotFoundError(DevicesServiceError): ...


class AlreadyExistsError(DevicesServiceError): ...


class PermissionDeniedError(DevicesServiceError): ...


class InvalidValueError(DevicesServiceError): ...
