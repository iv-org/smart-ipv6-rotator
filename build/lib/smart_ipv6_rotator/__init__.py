import argparse
from ipaddress import IPv6Address, IPv6Network
from random import choice, getrandbits, seed
from time import sleep
from typing import Any, Callable

import requests

from smart_ipv6_rotator.const import ICANHAZIP_IPV6_ADDRESS, IP, IPROUTE
from smart_ipv6_rotator.helpers import (
    PreviousConfigs,
    SavedRanges,
    check_ipv6_connectivity,
    clean_ranges,
    root_check,
    what_ranges,
)
from smart_ipv6_rotator.ranges import RANGES

SHARED_OPTIONS = [
    (
        "--services",
        {
            "type": str,
            "choices": list(RANGES.keys()),
            "required": False,
            "default": "google",
            "help": "IPV6 ranges of popular services. Example: --services google,twitter",
        },
    ),
    (
        "--ipv6-ranges",
        {
            "type": str,
            "required": False,
            "help": "Manually define external IPV6 ranges to rotate for.",
        },
    ),
    (
        "--skip-root",
        {
            "action": "store_true",
            "required": False,
            "help": "Example: --skip-root for skipping root check",
        },
    ),
    (
        "--no-services",
        {
            "action": "store_true",
            "required": False,
            "help": "Completely disables the --services flag.",
        },
    ),
]


def add_options(options) -> Callable[..., Any]:
    def _add_options(func) -> Any:
        parser = argparse.ArgumentParser()
        for option, kwargs in reversed(options):
            parser.add_argument(option, **kwargs)
        return parser.parse_args()

    return _add_options


def print_debug_info(memory_settings: dict):
    print("[DEBUG] Debug info:")
    for key, value in memory_settings.items():
        print(f"{key} --> {value}")


def run(
    my_ipv6_range: str,
    skip_root: bool = False,
    services: str | None = None,
    ipv6_ranges: str | None = None,
    no_services: bool = False,
) -> None:
    """Run the IPv6 rotator process."""

    root_check(skip_root)
    check_ipv6_connectivity()

    service_ranges = what_ranges(services, ipv6_ranges, no_services)

    clean_ranges(service_ranges, skip_root)

    seed()
    ipv6_network = IPv6Network(my_ipv6_range)
    random_ipv6_address = str(
        IPv6Address(
            ipv6_network.network_address
            + getrandbits(ipv6_network.max_prefixlen - ipv6_network.prefixlen)
        )
    )

    default_interface = IPROUTE.route("get", dst=choice(service_ranges))[0]  # type: ignore
    default_interface_index = int(default_interface.get_attrs("RTA_OIF")[0])
    default_interface_gateway = str(default_interface.get_attrs("RTA_GATEWAY")[0])
    default_interface_name = IP.interfaces[default_interface_index]["ifname"]

    memory_settings = {
        "random_ipv6_address": random_ipv6_address,
        "random_ipv6_address_mask": ipv6_network.prefixlen,
        "gateway": default_interface_gateway,
        "interface_index": default_interface_index,
        "interface_name": default_interface_name,
        "ipv6_subnet": my_ipv6_range,
    }

    # Save config now, will be cleaned if errors raised.
    PreviousConfigs(service_ranges).save(
        SavedRanges(**{**memory_settings, "ranges": service_ranges})
    )

    print_debug_info(memory_settings)

    try:
        IPROUTE.addr(
            "add",
            default_interface_index,
            address=random_ipv6_address,
            mask=ipv6_network.prefixlen,
        )
    except Exception as error:
        clean_ranges(service_ranges, skip_root)
        raise Exception(
            "[Error] Failed to add the new random IPv6 address. The setup did not work!\n"
            "        That's unexpected! Did you correctly configured the IPv6 subnet to use?\n"
            f"       Exception:\n{error}"
        )

    sleep(2)  # Need so that the linux kernel takes into account the new ipv6 route

    try:
        IPROUTE.route(
            "add",
            dst=ICANHAZIP_IPV6_ADDRESS,
            prefsrc=random_ipv6_address,
            gateway=default_interface_gateway,
            oif=default_interface_index,
            priority=1,
        )
    except Exception as error:
        clean_ranges(service_ranges, skip_root)
        raise Exception(
            "[Error] Failed to configure the test IPv6 route. The setup did not work!\n"
            f"       Exception:\n{error}"
        )

    sleep(2)

    try:
        check_new_ipv6_address = requests.get(
            f"http://[{ICANHAZIP_IPV6_ADDRESS}]",
            headers={"host": "ipv6.icanhazip.com"},
            timeout=5,
        )
    except requests.exceptions.RequestException as error:
        clean_ranges(service_ranges, skip_root)
        raise Exception(
            "[ERROR] Failed to send the request for checking the new IPv6 address! The setup did not work!\n"
            "        Your provider probably does not allow setting any arbitrary IPv6 address.\n"
            "        Or did you correctly configured the IPv6 subnet to use?\n"
            f"       Exception:\n{error}"
        )

    try:
        check_new_ipv6_address.raise_for_status()
    except requests.HTTPError:
        clean_ranges(service_ranges, skip_root)
        raise Exception(
            "[ERROR] icanhazip didn't return the expected status, possibly they are down right now."
        )

    response_new_ipv6_address = check_new_ipv6_address.text.strip()
    if response_new_ipv6_address == random_ipv6_address:
        print("[INFO] Correctly using the new random IPv6 address, continuing.")
    else:
        clean_ranges(service_ranges, skip_root)
        raise Exception(
            "[ERROR] The new random IPv6 is not used! The setup did not work!\n"
            "        That is very unexpected, check if your IPv6 routes do not have too much priority."
            f"       Address used: {response_new_ipv6_address}"
        )

    try:
        for ipv6_range in service_ranges:
            IPROUTE.route(
                "add",
                dst=ipv6_range,
                prefsrc=random_ipv6_address,
                gateway=default_interface_gateway,
                oif=default_interface_index,
                priority=1,
            )
    except Exception as error:
        clean_ranges(service_ranges, skip_root)
        raise Exception(
            f"[Error] Failed to configure the test IPv6 route. The setup did not work!\n"
            f"        Exception:\n{error}"
        )

    print(
        f"[INFO] Correctly configured the IPv6 routes for IPv6 ranges {service_ranges}.\n"
        "[INFO] Successful setup. Waiting for the propagation in the Linux kernel."
    )
    sleep(6)


def clean(
    skip_root: bool = False,
    services: str | None = None,
    ipv6_ranges: str | None = None,
    no_services: bool = False,
) -> None:
    """Clean your system for a given service / ipv6 ranges."""

    clean_ranges(what_ranges(services, ipv6_ranges, no_services), skip_root)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="IPv6 rotator for specific subnets - unblock restrictions on IPv6 enabled websites"
    )
    subparsers = parser.add_subparsers()

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument(
        "--my-ipv6-range",
        required=True,
        help="Your IPV6 range. Example: --my-ipv6-rang=2001:1:1::/64",
    )
    add_options(SHARED_OPTIONS)(run_parser)
    run_parser.set_defaults(func=run)

    clean_parser = subparsers.add_parser("clean")
    add_options(SHARED_OPTIONS)(clean_parser)
    clean_parser.set_defaults(func=clean)

    args = parser.parse_args()
    args.func(**vars(args))