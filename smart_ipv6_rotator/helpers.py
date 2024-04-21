import os
from dataclasses import asdict, dataclass
from time import sleep

import click
import requests
from tinydb import Query, TinyDB

from smart_ipv6_rotator.const import ICANHAZIP_IPV6_ADDRESS, IPROUTE
from smart_ipv6_rotator.ranges import RANGES


def root_check(skip_root: bool = False) -> None:
    if os.geteuid() != 0 and not skip_root:
        raise Exception(
            "[Error] Please run this script as root! It needs root privileges."
        )


def check_ipv6_connectivity() -> None:
    try:
        requests.get("http://ipv6.icanhazip.com", timeout=5)
    except requests.exceptions.RequestException:
        raise Exception(
            "[Error] You do not have IPv6 connectivity. This script can not work."
        )

    click.echo("[INFO] You have IPv6 connectivity. Continuing.")


def what_ranges(
    service: str | None = None, ipv6_ranges: str | None = None
) -> list[str]:
    """Works out what service ranges the user wants to use.

    Args:
        service (str | None, optional): Defaults to None.
        ipv6_ranges (str | None, optional): Defaults to None.

    Raises:
        Exception: Invalid params

    Returns:
        list[str]: IPV6 ranges
    """

    if not service and not ipv6_ranges:
        raise Exception("No service or ranges given.")

    ranges_: list[str] = []

    if service:
        if service not in RANGES:
            raise Exception(f"{service} isn't a valid service.")

        ranges_ = list(RANGES[service])

    if ipv6_ranges:
        ranges_ += ipv6_ranges.split(",")

    return ranges_


def clean_ranges(ranges_: list[str], skip_root: bool) -> None:
    """Cleans root.

    Args:
        ranges_ (list[str]):
        skip_root (bool):
    """

    root_check(skip_root)

    previous_config = PreviousConfigs(ranges_)

    previous = previous_config.get()
    if not previous:
        click.echo("[INFO] No cleanup of previous setup needed.")
        return

    try:
        IPROUTE.route(
            "del",
            dst=ICANHAZIP_IPV6_ADDRESS,
            prefsrc=previous.random_ipv6_address,
            gateway=previous.gateway,
            oif=previous.interface_index,
        )
    except:
        click.echo(
            """[Error] Failed to remove the test IPv6 subnet.
            May be expected if the route were not yet configured and that was a cleanup due to an error.
            """
        )

    try:
        for ipv6_range in previous.ranges:
            IPROUTE.route(
                "del",
                dst=ipv6_range,
                prefsrc=previous.random_ipv6_address,
                gateway=previous.gateway,
                oif=previous.interface_index,
            )
    except:
        click.echo(
            f"""[Error]  Failed to remove the configured IPv6 subnets {','.join(previous.ranges)}
            May be expected if the route were not yet configured and that was a cleanup due to an error
            """
        )

    try:
        IPROUTE.addr(
            "del",
            previous.interface_index,
            address=previous.random_ipv6_address,
            mask=previous.random_ipv6_address_mask,
        )
    except:
        click.echo("[Error] Failed to remove the random IPv6 address, very unexpected!")

    previous_config.remove()

    click.echo(
        "[INFO] Finished cleaning up previous setup.\n[INFO] Waiting for the propagation in the Linux kernel."
    )

    sleep(6)


@dataclass
class SavedRanges:
    ranges: list[str]
    random_ipv6_address: str
    gateway: str
    interface_index: int
    interface_name: str
    ipv6_subnet: str
    random_ipv6_address_mask: int


class PreviousConfigs:

    def __init__(
        self,
        ranges_: list[str],
    ) -> None:
        self.db = TinyDB("/tmp/smart-ipv6-rotator.json")
        self.ranges_ = ranges_

    def remove(self) -> None:
        self.db.remove(Query().ranges.all(self.ranges_))

    def save(self, to_save: SavedRanges) -> None:
        """Save a given service/ipv6 ranges for cleanup later.

        Args:
            ranges_ (list[str]): IPV6 ranges
        """

        self.remove()

        self.db.insert(asdict(to_save))

    def get(self) -> SavedRanges | None:
        result = self.db.search(Query().ranges.all(self.ranges_))
        if not result:
            return

        return SavedRanges(**result[0])
