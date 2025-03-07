def prefix_0x(to_prefix: str) -> str:
    if len(to_prefix) >= 2:
        if to_prefix[:2] == "0x":
            return to_prefix
    return f"0x{to_prefix}"


def un_prefix_0x(to_unprefixed: str) -> str:
    if len(to_unprefixed) >= 2:
        if to_unprefixed[:2] == "0x":
            return to_unprefixed[2:]
    return to_unprefixed
