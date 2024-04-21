import json
import os
from dataclasses import asdict, dataclass
from time import sleep

import requests

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
    except requests.Timeout:
        raise Exception(
            "[Error] You do not have IPv6 connectivity. This script can not work."
        )
    except requests.HTTPError:
        raise Exception(
            "[ERROR] icanhazip didn't return the expected status, possibly they are down right now."
        )

    print("[INFO] You have IPv6 connectivity. Continuing.")


def what_ranges(
    services: str | None = None,
    ipv6_ranges: str | None = None,
    no_services: bool = False,
) -> list[str]:
    """Works out what service ranges the user wants to use.

    Args:
        services (str | None, optional): Defaults to None.
        ipv6_ranges (str | None, optional): Defaults to None.
        no_services (bool, optional): Default to False

    Raises:
        Exception: Invalid params

    Returns:
        list[str]: IPV6 ranges
    """

    ranges_: list[str] = []

    if services and not no_services:
        for service in services.split(","):
            if service not in RANGES:
                raise Exception(f"{service} isn't a valid service.")

            ranges_ += list(RANGES[service])

    if ipv6_ranges:
        ranges_ += ipv6_ranges.split(",")

    if not ranges_:
        raise Exception("No service or ranges given.")

    return list(set(ranges_))


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
        print("[INFO] No cleanup of previous setup needed.")
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
        print(
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
        print(
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
        print("[Error] Failed to remove the random IPv6 address, very unexpected!")

    previous_config.remove()

    print(
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
    json_file = "/tmp/smart-ipv6-rotator.json"

    def __init__(
        self,
        ranges_: list[str],
    ) -> None:
        self.__ranges = ranges_

    def __get_raw(self) -> list[dict]:
        if not os.path.exists(self.json_file):
            return []

        with open(self.json_file, "r") as f_:
            return json.loads(f_.read())

    def __ranges_exist(self, results: dict) -> bool:
        return all(value in self.__ranges for value in results["ranges"])

    def remove(self) -> None:
        """Remove range from json file."""

        results = self.__get_raw()
        to_remove_index = next(
            (
                index
                for index, ranges in enumerate(results)
                if self.__ranges_exist(ranges)
            ),
            None,
        )

        if to_remove_index is not None:
            results.pop(to_remove_index)

            with open(self.json_file, "w") as f_:
                f_.write(json.dumps(results))

    def save(self, to_save: SavedRanges) -> None:
        """Save a given service/ipv6 ranges for cleanup later.

        Args:
            ranges_ (list[str]): IPV6 ranges
        """

        self.remove()

        results = self.__get_raw()
        results.append(asdict(to_save))

        with open(self.json_file, "w") as f_:
            f_.write(json.dumps(results))

    def get(self) -> SavedRanges | None:
        """Gets saved ranges.

        Returns:
            SavedRanges | None: Save ranges.
        """

        results = self.__get_raw()

        for result in results:
            if self.__ranges_exist(result):
                return SavedRanges(**result)
