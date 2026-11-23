from rest_framework.exceptions import APIException


class Conflict(APIException):
    """409: the request is fine but the state of the world no longer allows it
    (for example, another provider accepted the booking first)."""

    status_code = 409
    default_detail = "This request conflicts with the current state of the booking."
    default_code = "conflict"
