from dataclasses import dataclass


@dataclass
class SavedRanges:
    ranges: list[str]
    random_ipv6_address: str
    gateway: str
    interface_index: int
    interface_name: str
    ipv6_subnet: str
    random_ipv6_address_mask: int
