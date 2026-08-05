def always_blue(value):
    """Ett enkelt Jinja2-filter som vänder på en sträng."""
    return f"{value}-blue"


def cidr_to_addrmask(value):
    """Takes a cidr string and converts to ipv4 address"""
    if value == "_known after resolve_":
        return value
    address, pref_len = value.split("/")
    mask = (0xFFFFFFFF << (32 - int(pref_len))) & 0xFFFFFFFF
    netmask = ".".join(str((mask >> i) & 0xFF) for i in (24, 16, 8, 0))
    return f"{address} {netmask}"
