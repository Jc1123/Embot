import re


TIME_MULTIPLIERS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "M": 2592000,
    "a": 31536000,
}


def parse_duration(
    value: str
) -> int | None:

    match = re.fullmatch(
        r"(\d+)([a-zA-Z])",
        value.strip()
    )

    if not match:
        return None

    quantity = int(
        match.group(1)
    )

    unit = match.group(2)

    multiplier = TIME_MULTIPLIERS.get(
        unit
    )

    if multiplier is None:
        return None

    return quantity * multiplier