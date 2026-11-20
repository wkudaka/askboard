class ServiceError(Exception):
    """Base class for errors the API maps to 4xx responses."""


class NotFoundError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class InvalidInputError(ServiceError):
    pass
