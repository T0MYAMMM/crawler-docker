from enum import Enum

class ProxyType(Enum):
    """Enumeration for different proxy types in rotation cycle."""
    NONE = "none"
    LOCAL = "local"
    ZYTE = "zyte"