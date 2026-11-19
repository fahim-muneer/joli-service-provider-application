import re

PHONE_ERROR = "Enter a valid 10-digit Indian mobile number."


def normalize_phone(raw) -> str:
    """Return the number as +91XXXXXXXXXX, or raise ValueError.

    Accepted: 9876543210, 98765 43210, 09876543210, 919876543210,
    +91 98765 43210, +91-98765-43210.
    Rejected: anything that isn't a 10-digit mobile number starting 6-9.
    Idempotent: normalize_phone(normalize_phone(x)) == normalize_phone(x).
    """
    value = re.sub(r"[\s\-().]", "", str(raw or ""))

    if value.startswith("+"):
        if not value.startswith("+91"):
            raise ValueError(PHONE_ERROR)
        value = value[3:]
    elif len(value) == 12 and value.startswith("91"):
        value = value[2:]
    elif len(value) == 11 and value.startswith("0"):
        value = value[1:]

    if not re.fullmatch(r"[6-9]\d{9}", value):
        raise ValueError(PHONE_ERROR)

    return "+91" + value